from flask import Flask, render_template, request, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
import qrcode
import cv2 
import numpy as np
import io
import io
import pyotp

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///qr_codes.db'
db = SQLAlchemy(app)

class QRCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(255), nullable=False)
    sender_name = db.Column(db.String(255), nullable=True)
    subject = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=True)
    email = db.Column(db.String(255), nullable=True)
    expiration_time = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<QRCode {self.data}>'

with app.app_context():
    db.drop_all()
    db.create_all()

@app.route('/')
def index():
    qr_codes = QRCode.query.all()
    return render_template('index.html', qr_codes=qr_codes)

@app.route('/generate', methods=['POST'])
def generate():
    subject = request.form['subject']
    body = request.form['body']
    email = request.form['email']
    expiration_time = request.form['expiration_time']
    sender_name = request.form['sender_name']

    qr_data = f"Sender Name: {sender_name}\nSubject: {subject}\nBody: {body}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    qr_code = QRCode(data=qr_data, sender_name=sender_name, subject=subject, body=body, email=email, expiration_time=expiration_time)
    db.session.add(qr_code)
    db.session.commit()

    return send_file(img_io, mimetype='image/png')

@app.route('/scan', methods=['POST'])
def scan():
    # Get the image file from the request
    image_file = request.files['image']
    # Convert the image file to a numpy array
    image_bytes = image_file.read()
    image_np = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    # Create a QR code detector
    detector = cv2.QRCodeDetector()
    # Detect and decode QR codes
    data, vertices_array, binary_qrcode = detector.detectAndDecode(image)
    if vertices_array is not None:
        # QR code detected
        # Check if the QR data is an Authenticator URI
        if pyotp.utils.parse_uri(data.decode('utf-8')):
            # It's an Authenticator URI, fetch the QR code data from the database
            qr_code = QRCode.query.filter_by(data=data.decode('utf-8')).first()
            if qr_code:
                return render_template('qr_info.html', sender_name=qr_code.sender_name, subject=qr_code.subject, body=qr_code.body, email=qr_code.email, expiration_time=qr_code.expiration_time)
            else:
                return render_template('error.html', error='QR code data not found in the database'), 404
        else:
            # It's not an Authenticator URI, handle the QR data as before
            parts = data.split('\n')
            sender_name = parts[0].split(': ')[1]
            subject = parts[1].split(': ')[1]
            body = parts[2].split(': ')[1]
            return render_template('qr_info.html', sender_name=sender_name, subject=subject, body=body)
    else:
        # No QR code detected
        return render_template('error.html', error='No QR code detected'), 404
        
@app.route('/authenticator', methods=['GET'])
def generate_authenticator_qr():
    # Generate a secret key for OTP
    secret_key = pyotp.random_base32()
    # Create a URI for the Authenticator app
    uri = pyotp.totp.TOTP(secret_key).provisioning_uri(name='Prevent Phishing', issuer_name='ABC Bank')
    # Create a QR code from the URI
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    # Save the Authenticator URI in the database
    qr_code = QRCode(data=uri)
    db.session.add(qr_code)
    db.session.commit()

    # Return the QR code image
    return send_file(img_io, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)