from flask import Flask, render_template, request, send_file, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
import qrcode
import cv2
import numpy as np
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
    qr_code = QRCode(data=qr_data, sender_name=sender_name, subject=subject, body=body, email=email, expiration_time=expiration_time)
    db.session.add(qr_code)
    db.session.commit()

    unique_id = qr_code.id  # Assuming 'id' is the primary key of the QRCode table
    qr_url = url_for('qr_info_page', unique_id=unique_id, _external=True)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

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
        qr_data = data
        parts = qr_data.split('\n')
        sender_name = parts[0].split(': ')[1]
        subject = parts[1].split(': ')[1]
        body = parts[2].split(': ')[1]
        # Generate a QR code with the URL of the qr_info_page
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr_url = url_for('qr_info_page', qr_data=qr_data, _external=True)
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)

        # Return the QR code image
        return send_file(img_io, mimetype='image/png')
        #return render_template('qr_info.html', sender_name=sender_name, subject=subject, body=body)
    else:
        # No QR code detected
        return jsonify({'error': 'No QR code detected'}), 404

@app.route('/qr_info/<int:unique_id>', methods=['GET'])
def qr_info_page(unique_id):
    qr_code = QRCode.query.get(unique_id)
    if qr_code:
        sender_name = qr_code.sender_name
        subject = qr_code.subject
        body = qr_code.body
        return render_template('qr_info.html', unique_id=unique_id, sender_name=sender_name, subject=subject, body=body)
    else:
        return render_template('error.html', error='QR code data not found'), 404

if __name__ == '__main__':
    app.run(debug=True)