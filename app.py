from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from forms.forms import RegistrationForm, BrosurForm  
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import StringField, TextAreaField
from sqlalchemy.exc import IntegrityError
from models.models import db, User, BlogPost
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/profile_images'
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

#Menu profil
@app.route('/profile')
def profile():
    return render_template('profile.html')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#Menu Home (Index)
@app.route('/')
def index():
    posts = BlogPost.query.all()
    return render_template('guest.html', posts=posts)

#Register ketika tidak mempunyai akun
@app.route('/register', methods=['GET', 'POST'])
def register():
    print("masuk regis")
    form = RegistrationForm()
    if form.validate_on_submit():
        print("masuk regis submit")
        allowed_roles = ['admin', 'author']
        if form.role.data not in allowed_roles:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('register'))
        
        existing_user_username = User.query.filter_by(username=form.username.data).first()
        existing_user_email = User.query.filter_by(email=form.email.data).first()

        if existing_user_username:
            flash('Nama pegguna sudah di gunakan.', 'danger')
            return redirect(url_for('register'))

        if existing_user_email:
            flash('Email pengguna sudah digunakan', 'danger')
            return redirect(url_for('register'))

        if form.password.data != form.confirm_password.data:
            print("masuk regis validasi")
            flash('Password dan konfirmasi password tidak sesuai.', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')

        try:
            new_user = User(
                username=form.username.data,
                email=form.email.data,
                password=hashed_password,
                role=form.role.data,
                approved=False
            )
            db.session.add(new_user)
            db.session.commit()

            if form.role.data == 'author':
                flash('Akun berhasil dibuat dan menunggu persetujuan admin.', 'success')

            return redirect(url_for('login'))
        except IntegrityError as e:
            flash('Error creating user. Please try again.', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html', form=form)


#Login User
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            if user.role == 'admin':
                login_user(user)
                next_page = request.args.get('next')
                if next_page:
                    return redirect(next_page)
                else:
                    return redirect(url_for('admin'))
            elif user.role == 'author' and user.approved:
                login_user(user)
                return redirect(url_for('author'))
            elif user.role == 'author' and not user.approved:
                flash('Akun Anda belum disetujui oleh admin. Harap tunggu persetujuan admin.', 'danger')
                return redirect(url_for('index'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html', error=error)

#LogOut User
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

#Menu Author Untuk User Author
@app.route('/author', methods=['GET', 'POST'])
@login_required
def author():
    form = BrosurForm()

    authors = User.query.filter_by(role='author').all()
    if form.validate_on_submit():
        brosur = form.brosur.data
        handle_brosur_upload(brosur)

        if form.title.data and form.content.data:
            add_post({
                'title': form.title.data,
                'content': form.content.data,
                'image': current_user.brosur_filename
            })

    posts = BlogPost.query.filter_by(author_id=current_user.id).all()
    return render_template('author.html', posts=posts, form=form, authors=authors)

def handle_brosur_upload(brosur):
    if brosur:
        filename = secure_filename(brosur.filename)
        brosur_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        brosur.save(brosur_path)

        current_user.brosur_filename = filename
        db.session.commit()

        flash('Brosur berhasil diupload.', 'success')

#Menambahkan Postingan
def add_post(data):
    new_post = BlogPost(
        title=data['title'],
        content=data['content'],
        image=data['image'],
        author_id=current_user.id
    )
    db.session.add(new_post)
    db.session.commit()

    flash('Post added successfully.', 'success')
    return redirect(url_for('author'))

#Melihat Postingan
@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    post.views += 1
    db.session.commit()
    return render_template('post.html', post=post)

#Edit Postingan
@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = BlogPost.query.get_or_404(post_id)

    if current_user != post.author:
        abort(403) 

    form = BrosurForm()

    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data

        if form.brosur.data:
            handle_brosur_upload(form.brosur.data)
            post.image = current_user.brosur_filename

        db.session.commit()
        flash('Post berhasil diperbarui!', 'success')

        return redirect(url_for('author'))

    form.title.data = post.title
    form.content.data = post.content

    return render_template('edit_post.html', form=form, post=post)

#Delete Postingan
@app.route('/admin/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = BlogPost.query.get_or_404(post_id)
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Post berhasil dihapus.', 'success')
    return redirect(url_for('admin'))

#Menu Admin Untuk User Admin
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        return redirect(url_for('login'))
    authors = User.query.filter_by(role='author').all()
    posts = BlogPost.query.all()
    return render_template('admin.html', authors=authors, posts=posts)

#Delete User Author
@app.route('/admin/delete_author/<int:user_id>', methods=['POST'])
@login_required
def delete_author(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    author_to_delete = User.query.get_or_404(user_id)

    if request.method == 'POST':
        db.session.delete(author_to_delete)
        db.session.commit()

        flash(f'Author {author_to_delete.username} deleted successfully.', 'success')
        return redirect(url_for('admin'))

    flash('Invalid request to delete author.', 'danger')
    return redirect(url_for('admin'))

#Melihat User Author
@app.route('/admin/view_author/<int:user_id>')
@login_required
def view_author(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    author = User.query.get_or_404(user_id)
    posts = BlogPost.query.filter_by(author_id=author.id).all()
    return render_template('view_author.html', author=author, posts=posts)

#Approved User Author Agar Bisa Login
@app.route('/admin/approve_author/<int:user_id>', methods=['GET', 'POST'])
@login_required
def approve_author(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('login'))

    author_to_approve = User.query.get_or_404(user_id)
    author_to_approve.approved = True
    db.session.commit()

    flash(f'Akun author {author_to_approve.username} telah disetujui.', 'success')
    return redirect(url_for('admin'))



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False)
