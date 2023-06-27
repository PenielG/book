import re,random,os,requests,json
from functools import wraps
from flask import render_template, request, redirect, flash,make_response,session,url_for
from sqlalchemy.sql import text
from bookapp import app, csrf
from bookapp.models import db,Book,User,Reviews,Category,Donation

from bookapp.forms import SignupForm,ProfileForm
from werkzeug.security import generate_password_hash, check_password_hash


# from bookapp.forms import ContactForm





@app.route("/donate", methods=['POST','GET'])
def donation():
    useronline = session.get('userid')    
    userdeets = db.session.query(User).get(useronline)
    if request.method =='GET':
        return render_template("user/donation.html",userdeets=userdeets)
    else: #retrieve form data
        fullname = request.form.get("fullname")
        email = request.form.get("email")
        amount = request.form.get('amount')
                 
        if request.form.get('userid') =="":
            userid = None
        else:
            userid= request.form.get('userid')
            
        refno = int(random.random()*100000000)
        #create a new donation instance
        don = Donation(don_amt=amount,don_userid=userid,don_fullname=fullname,don_email=email,don_refno=refno,don_status='pending')
        db.session.add(don)
        db.session.commit()     
        #save the refno in a session so that we can retrieve the details on the next page
        session['ref']   = refno
        return redirect("/payment")
       
            
@app.route("/payment")   
def make_payment():
    userdeets = db.session.query(User).get(session.get('userid'))
    if session.get('ref') !=None:
        ref = session['ref']
        #TO DO: we want to get the details of the transaction and display to the user
        trxdeets = db.session.query(Donation).filter(Donation.don_refno==ref).first()
        return render_template("user/payment.html", trxdeets=trxdeets,userdeets=userdeets)
    else:
        return redirect("/donate")

@app.route("/paystack", methods=['POST'])
def paystack():
    if session.get('ref') != None:
        ref = session['ref']
        trx = db.session.query(Donation).filter(Donation.don_refno==ref).first()
        email = trx.don_email
        amount = trx.don_amt
        #we want to connect to paystack api
        url ="https://api.paystack.co/transaction/initialize"
        
        headers = {"Content-Type": "application/json","Authorization":"Bearer sk_test_671dd0a9961b0a31479c06b90a00f5ec0ba4280b"}
        
        data = { "email": email, "amount": amount*100, "reference":ref }
        response = requests.post(url, headers=headers, data=json.dumps(data))
        rspjson = response.json()
        if rspjson['status'] == True:
            paygateway = rspjson['data']['authorization_url']
            return redirect(paygateway)
        else:
            return rspjson    
    else:
        return redirect("/donate")
    
    


@app.route("/landing")
def paystack_landing():
    ref=session.get('ref')
    if ref ==None:
        return redirect('/donate')
    else:
        headers={"Content-Type": "application/json","Authorization":"Bearer sk_test_671dd0a9961b0a31479c06b90a00f5ec0ba4280b"}
        verifyurl= "https://api.paystack.co/trasaction/verify/"+str(ref)
        response=requests.get(verifyurl,headers=headers)
        rspjson=response.get_json()
        # rspjson = json.loads(response.text)
        return rspjson
        if rspjson['status']==True: #payment was successful
            return rspjson
        else: #payment was not successful
            return "payment was not successful"



@app.route("/explore/",methods=['POST','GET'])
def explore():
    books=db.session.query(Book).filter(Book.book_status=='1').order_by(Book.book_id.desc()).limit(4).all()
    cats=db.session.query(Category).all()
    return render_template('user/explore.html',books=books, cats=cats)


@app.route('/search/book')
def search_book():
    cate = request.args.get('category')
    title = request.args.get('title') 
    search_title = "%"+title+"%" # "%{}%".format(title)
    #run query
    if cate =="":
        result = db.session.query(Book).filter(Book.book_title.ilike(search_title)).all()
    else:
        result = db.session.query(Book).filter(Book.book_catid ==cate).filter(Book.book_title.ilike(search_title)).all()

    #result = [<Book 1>, <Book 2>, <Book 3>] 
    toreturn =""
    for r in result:
        toreturn = toreturn + f"<div class='col'><img src='/static/collections/{r.book_cover}' class='img-fluid bk'><div class='deets'><h6><a href='/review/{r.book_id}'>{r.book_title}</a></h6><p><i>{r.catdeets.cat_name}</i></p><p><button class='btn btn-sm btn-warning'{len(r.bookreviews)}>Reviews</button></p></div></div>"
    
    return toreturn






def login_required(f):
    @wraps(f)  #from functools import wraps
    def login_decorator(*args,**kwargs): #"**kwargs" keyworded argument for unpacking dictionary,*args for unpacking a list
        if session.get("user_id") and session.get('user_loggedin'):
           return f(*args,**kwargs)
        else:
            flash("Access Denied, Please login")
            return redirect ("/login")
    return login_decorator

@app.route("/")
def home():

    book=db.session.query(Book).filter(Book.book_status=='1').all()
    useronline=session.get('user_id')
    userdeets=db.session.query(User).get(useronline)
    #we will connect to the endpoint http://127.0.0.1:5000/api/v1.0/listall in order to fetch from the store
    headers= {'Content-Type': 'application/json'}
    response=requests.get('http://127.0.0.1:5000/api/v1.0/listall',headers,auth=('bookworm','python'))

    partner_stores=response.json()

    return render_template("user/home.html",book=book,userdeets=userdeets,partner_stores=partner_stores)


@app.route("/reviews/<bookid>")
def reviews(bookid):
    bookdeets=db.session.query(Book).get_or_404(bookid)
    return render_template("user/reviews.html",bookdeets=bookdeets)

@app.route("/submitreview",methods=['POST'])
@login_required
def submit_review():
    title=request.form.get('review_title')
    text=request.form.get('review')
    bookid=request.form.get('bookid')
    useronline=session.get('user_id')
    #insert this review
    review=Reviews(rev_text=text,rev_title=title,rev_bookid=bookid,rev_userid=useronline)
    db.session.add(review)
    db.session.commit()
    flash("Thank you, your review has been submitted")
    return redirect('/dashboard')


@app.route("/dashboard")
@login_required
def dashboard():
    useronline=session.get('user_id')
    userdeets=db.session.query(User).get(useronline)
    return render_template("user/dashboard.html",userdeets=userdeets)



@app.route("/profile/",methods=['GET','POST'])
@login_required
def profile():
    pform=ProfileForm()
    useronline=session.get('user_id')
    userdeets=db.session.query(User).get(useronline)
    if request.method=='GET':
      
        return render_template("user/profile.html",pform=pform,userdeets=userdeets)   
    else:
        if pform.validate_on_submit():
            fullname=request.form.get('fullname')#pform.fullname.data
            picture=request.files.get('pix')#pform.pix.filename
            filename=pform.pix.data.filename
            picture.save("bookapp/static/images/profile/"+filename)
            userdeets.user_fullname=fullname #userdeets.user_pwd=hash of what is comming iin
            userdeets.user_pix=filename
            db.session.commit()
            flash("Profile updated")
            return redirect("/dashboard")
        else:
            return render_template("user/profile.html",pform=pform,userdeets=userdeets)   




@app.route("/login/",methods=['GET','POST'])
def login():
    if request.method=='GET':
        return render_template("user/loginpage.html")
    else:
        #we are using the below method because we are using non flask form
        username=request.form.get('email')#give form input name='email'
        password=request.form.get('password')#give form input name='password'
        deets=db.session.query(User).filter(User.user_email==username).first()#will give <userid> an object
        if deets:
            hashedpwd=deets.user_pwd
            chk=check_password_hash(hashedpwd,password)#Returns True/False
            if chk:
                session['user_loggedin']=True
                session['user_id']=deets.user_id
                return redirect ("/dashboard")
            else:
                flash("Invalid Password")
                return redirect ("/login")
        else:
            flash("Invalid Username")
            return redirect ("/login")


# @app.route("/login/",methods=['POST','GET'])
# def login():
#     if request.method=='GET':
#         return render_template('/user/loginpage.html')
#     else:
#         username=request.form.get('email')
#         password=request.form.get('password')
#         deets=db.session.query(User).filter(User.user_email==username).first()
#         if deets:
#             hashpwd=deets.user_pwd
#             chk=check_password_hash(hashpwd,password)
#             if chk:
#                session['user_id']=deets.user_id
#                session['user_loggedin']=True
#                return redirect("/dashboard/")
#             else:
#               flash("Invalid Password")
#               return redirect("/login/")
#         else:
#             flash('Invalid Username')
#             return redirect("/login/")
    
        
        






# @app.route("/register/",methods=['GET','POST'])
# def register():
#             signupform=SignupForm()
#             if request.method=='GET':
#                 return render_template("user/signup.html",signupform=signupform)
#             else:
#                 if signupform.validate_on_submit():
#                     userpass=request.form.get('password')
#                     u=User(user_fullname=request.form.get('fullname'),user_email=request.form.get('email'),user_pwd=generate_password_hash(userpass))
#                     db.session.add(u)
#                     db.session.commit()
#                      #log user in
#                     session['user_id']=u.user_id
#                     session['user_loggedin']=True
#                     flash("Your account has been suceesfully created")
#                     return redirect('/login/')
#                 else:
#                     flash("Invalid Credentials")
#                     return render_template("user/signup.html",signupform=signupform)
                    
            
            



      
@app.route("/register/",methods=['GET','POST'])
def register():
         signupform=SignupForm()
         if request.method=='GET':
            return render_template("user/signup.html",signupform=signupform)
         else:
            if signupform.validate_on_submit():
                userpass=request.form.get('password')
                u=User(user_fullname=request.form.get("fullname"),user_email=request.form.get('email'), user_pwd=generate_password_hash(userpass))
                db.session.add(u)
                db.session.commit()
                #log the user in and redirect to dashboard
                session['user_id']=u.user_id
                session['user_loggedin']=True
                return redirect("/dashboard")
            

             # flash("An account has been created for you")
             # return redirect("/login/")
            else:
                return render_template("user/signup.html",signupform=signupform)
        
@app.route("/signout")
def signout():
    if session.get('user_id') or session.get('user_loggedin'):
        session.pop('user_id', None)
        session.pop('user_id',None)
    return redirect("/")
