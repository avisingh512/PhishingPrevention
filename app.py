from flask import Flask, render_template, request, send_file, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
import qrcode
import cv2
import numpy as np
import io
from flask_mail import Mail
import smtplib
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email import encoders
import random

app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'wells.pocproject@gmail.com'
app.config['MAIL_PASSWORD'] = 'fluurehrnsteyghs'
app.config['MAIL_DEFAULT_SENDER'] = 'wells.pocproject@gmail.com'

mail = Mail(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///qr_codes.db'
db = SQLAlchemy(app)

class QRCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(255), nullable=False)
    send_to = db.Column(db.String(255), nullable=True)
    body = db.Column(db.Text, nullable=True)
    expiration_time = db.Column(db.String(255), nullable=True)
    purpose = db.Column(db.String(255), nullable=True)

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
    body = request.form['body']
    send_to = request.form['send_to']
    purpose = request.form['purpose']
    expiration_time = 10 #request.form['expiration_time'] hardcode for now

    # Generate a random 6-digit number for the unique_id
    while True:
        unique_id = random.randint(100000, 999999)
        if not QRCode.query.get(unique_id):
            break
    qr_data = f"Sent From: {app.config['MAIL_USERNAME']}\nSent To: {send_to}\nBody: {body}"
    qr_code = QRCode(id=unique_id, data=qr_data, send_to=send_to, purpose=purpose, body=body, expiration_time=expiration_time)
    db.session.add(qr_code)
    db.session.commit()

    unique_id = qr_code.id
    qr_url = url_for('qr_info_page', unique_id=unique_id, _external=True)
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert QR code image to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes)
    img_bytes = img_bytes.getvalue()

    # Create email message
    msg = MIMEMultipart()
    msg['Subject'] = purpose
    msg['From'] = 'wells.pocproject@gmail.com'
    msg['To'] = send_to

    # Read the HTML template based on the purpose
    with open(f"templates/{purpose}.html", "r") as file:
        html = file.read()

    html = html.replace("{{ unique_id }}", str(unique_id))

    html_part = MIMEText(html, 'html')
    msg.attach(html_part)

    # Add QR code image
    img_part = MIMEImage(img_bytes, name="qr_code.png", _encoder=encoders.encode_base64)
    img_part.add_header('Content-ID', '<qr_code>')
    msg.attach(img_part)

    # Send email
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.starttls()
        smtp.login('wells.pocproject@gmail.com', 'fluurehrnsteyghs')
        smtp.send_message(msg)

    return 'Email sent successfully'

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
        send_to = parts[0].split(': ')[1]
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
        #return render_template('qr_info.html', send_to=send_to, subject=subject, body=body)
    else:
        # No QR code detected
        return jsonify({'error': 'No QR code detected'}), 404

@app.route('/qr_info/<int:unique_id>', methods=['GET'])
def qr_info_page(unique_id):
    qr_code = QRCode.query.get(unique_id)
    if qr_code:
        send_to = qr_code.send_to
        purpose = qr_code.purpose
        body = qr_code.body
        return render_template('qr_info.html', unique_id=unique_id, send_to=send_to, purpose=purpose, body=body)
    else:
        return render_template('error.html', error='QR code data not found'), 404

if __name__ == '__main__':
    app.run(debug=True)