#!p3_vir_env/bin/python3

import os
import getpass

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import base64
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import visidata

from models import Passwords, User, Base

#____________________________________________
#FOR PROFILING PURPOSES
#call snakeviz cProfile.prof in terminal to view results of profile
import cProfile, pstats, io
pr = cProfile.Profile()
pr.enable()
#____________________________________________

#TODO before deployment:

#add if statement or try except statement if a user tries to create a username that is already taken

#prevent user from manually accessing the database to delete things. Even though they cannot read passwords, they can still add and delete and edit stuff
#       Maybe do this by making the database only readable/writable by this application


#MUST RUN THIS LINE IN COMMANDLINE BEFORE CALLING THIS FILE
#export PYTHONPATH=~/Desktop/visidata/


#Set Up Session
engine = create_engine('sqlite:///passwords.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()


def hash_pw(unhashed):
#encrypt password and store encyption in database with username and salt. Take input password and hash it and check against hashed password in database to verify user
#use password to generate key that encrypts passwords table
    hashed = bcrypt.hashpw(unhashed.encode('UTF-8'), bcrypt.gensalt())
    return hashed


def verify_hash(password, hashed):
    if bcrypt.hashpw(password.encode('UTF-8'), hashed) == hashed:
        return True
    else:
        return False


def generate_key(password, salt):
#Generate a key. Requires a password and a salt
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
    key = base64.urlsafe_b64encode(kdf.derive(password.encode('UTF-8')))
    return key


def encrypt(unencrypted, key):
#Takes variable to be encrpyted and the key
    f = Fernet(key)
    return f.encrypt(unencrypted.encode('UTF-8'))


def decrypt(undecrypted, key):
#Takes the variable to be decrypted and the key
    f = Fernet(key)
    return f.decrypt(undecrypted).decode('UTF-8')


def validate_user(input_un, input_pass):
    try:
        user = session.query(User).filter_by(user_username=input_un).first()
        hashed_password = user.user_password
        if verify_hash(input_pass, hashed_password):
            return True
        else:
            return False
    except:
        print('Validate Failed')
        return False


def create_user(new_username, new_password):
    salt = os.urandom(16)
    hashed_password = hash_pw(new_password)
    new_user = User(new_username, hashed_password, salt)
    session.add(new_user)
    session.commit()


def main():
    print("Enter 'New' To Create New Account")
    current_user_username = input('Username: ')
    if current_user_username == 'New' or current_user_username == 'new':
        new_username = input('New Username: ')
        new_password = getpass.getpass()
        create_user(new_username, new_password)
        print('You have been registered!')
        current_user_username = input('Username: ')
    current_user_password = getpass.getpass()
    if validate_user(current_user_username, current_user_password):
        current_user = session.query(User).filter_by(user_username=current_user_username).first()
        vs = AddressBookSheet(current_user, current_user_password)
        visidata.run([vs])
    else:
        print('Invalid Login')
        main()


class AddressBookSheet(visidata.SqliteSheet):
	
    def __init__(self, current_user, current_user_password):
        super().__init__("passwords", visidata.Path("passwords.sqlite"), "passwords")
        self.current_user = current_user
        self.current_user_id = current_user.id
        self.current_user_password = current_user_password
        self.current_key = generate_key(current_user_password, current_user.user_salt)
        self.command("A", "add_entry(input('Site: '), input('Username: '), input('Password: '), current_user_id)", "Add A New Entry")
        self.command("d", "delete_entry(cursorRow[0])", "Delete Current Entry")
        self.command('e', 'edit_field(current_user_id)', 'Edit This Cell')

    # TODO: Replace this funtion with one to call in visitdata.Column getter and put needed variables in __init__ as class variables
    def make_decrypt(self, user, item_number):
        def temp_decrypt(r, self=self, salt=self.current_user.user_salt, item_number=item_number):
            return decrypt(r[item_number], self.current_key)
        return temp_decrypt

    def reload(self):
        super().reload()
        user = self.current_user   
        self.rows = [r for r in self.rows if r[4] == self.current_user.id]
        c1 = visidata.Column('Site', getter=self.make_decrypt(user, 1))
        c1.internal_field = 'site'
        c2 = visidata.Column('Username', getter=self.make_decrypt(user, 2))
        c2.internal_field = 'site_username'
        c3 = visidata.Column('Password', getter=self.make_decrypt(user, 3))
        c3.internal_field = 'site_password'
        self.columns = [c1, c2, c3]

    def add_entry(self, site, username, password, user_id):
        user = self.current_user
        newentry = Passwords(encrypt(site, self.current_key), encrypt(username, self.current_key), encrypt(password, self.current_key), user_id)
        session.add(newentry)
        session.commit()
        self.reload()

    def delete_entry(self, id):
        session.query(Passwords).filter_by(id=id).delete()
        session.commit()
        self.reload()

    def edit_field(self, user_id):
        user = self.current_user
        row_id = self.cursorRow[0]      
        new_val = self.editCell(self.cursorVisibleColIndex)
        encrypted_new_val = encrypt(new_val, self.current_key)
        field = self.cursorCol.internal_field
        edit_field_attr = getattr(Passwords, field)
        visidata.status(row_id)
        session.query(Passwords).filter_by(id=row_id).update({edit_field_attr: encrypted_new_val})
        session.commit()
        self.reload()


if __name__=='__main__':
    main()
    
#_____________________
#MORE PROFILING
pr.disable()
s = io.StringIO()
sortby = 'time'
ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
ps.dump_stats("cProfile.prof")
print(s.getvalue())
#_____________________
