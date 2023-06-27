'''This module will generate  a mini webserver'''
from bookapp import app




if __name__=="__main__":
    app.run(debug=True,port=8082)