from flask import Flask,render_template, request, jsonify
from PyPDF2 import PdfReader, PdfWriter
import PyPDF2
import os
import shutil
import tempfile
from pdf2image import convert_from_path
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import  PyPDF2
from flask import send_file
from img2pdf import convert

from reportlab.lib.pagesizes import A4
from PIL import Image

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/merge', methods=['POST','GET'])
def merge_pdfs():
    if request.method == "POST":
        pdf_files = request.files.getlist('files')
        merged_pdf = PdfWriter()

        for file in pdf_files:
            if file and allowed_file(file.filename):
                pdf_reader = PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    merged_pdf.add_page(page)

        output_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'merged.pdf')
        with open(output_pdf_path, 'wb') as output_pdf_file:
            merged_pdf.write(output_pdf_file)

        return jsonify({'message': 'PDFs merged successfully', 'merged_pdf_path': output_pdf_path})
    return render_template('merge.html')

@app.route('/split', methods=['POST', 'GET'])
def split_pdf():
    if request.method == "POST":
        input_pdf = request.files['file']
        split_mode = request.form.get('splitMode')
        custom_ranges = request.form.get('ranges')

        if split_mode == "ranges" and custom_ranges:
            try:
                ranges = parse_custom_ranges(custom_ranges)
            except ValueError:
                return jsonify({'error': 'Invalid custom ranges format'}), 400
        else:
            ranges = None

        pdf_reader = PdfReader(input_pdf)

        if ranges:
            for start, end in ranges:
                output_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f'pages_{start}-{end}.pdf')
                output_pdf = PdfWriter()

                for page_num in range(start - 1, end):
                    output_pdf.add_page(pdf_reader.pages[page_num])

                with open(output_pdf_path, 'wb') as output_pdf_file:
                    output_pdf.write(output_pdf_file)
        else:
            for page_num in range(len(pdf_reader.pages)):
                output_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f'page_{page_num + 1}.pdf')
                output_pdf = PdfWriter()
                output_pdf.add_page(pdf_reader.pages[page_num])

                with open(output_pdf_path, 'wb') as output_pdf_file:
                    output_pdf.write(output_pdf_file)

        return jsonify({'message': 'PDF split successfully', 'output_folder': app.config['UPLOAD_FOLDER']})

    return render_template('split.html')

def parse_custom_ranges(custom_ranges):
    ranges = []
    for part in custom_ranges.split(','):
        if '-' in part:
            start, end = part.split('-')
            start = int(start.strip())
            end = int(end.strip())
            ranges.append((start, end))
        else:
            page_num = int(part.strip())
            ranges.append((page_num, page_num))
    return ranges

@app.route('/extract_text', methods=['POST','GET'])
def extract_text():
    if request.method == "POST":
        input_pdf = request.files['file']
        form_data = request.form

        pdf_reader = PyPDF2.PdfReader(input_pdf)
        text = ''

        num = min(len(pdf_reader.pages),int(form_data['pages']))
        for page_num in range(num):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()

        return jsonify({'text': text})
    return render_template('extract.html')

@app.route('/reduce_size', methods=['POST','GET'])
def reduce_size():
    if request.method == "POST":
        input_pdf = request.files['file']
        temp_dir = tempfile.mkdtemp()
        input_pdf_path = os.path.join(temp_dir, 'input.pdf')
        output_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'reduced.pdf')

        input_pdf.save(input_pdf_path)

        with open(input_pdf_path, 'rb') as infile:
            pdf_reader = PyPDF2.PdfReader(infile)
            writer = PyPDF2.PdfWriter()

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page.compress_content_streams()  # Compress content of each page
                writer.add_page(page)

            with open(output_pdf_path, 'wb') as outfile:
                writer.write(outfile)

        shutil.rmtree(temp_dir)

        return jsonify({'message': 'PDF size reduced successfully', 'output_pdf_path': output_pdf_path})
    return render_template('reduce.html')

@app.route('/uploads/<filename>', methods=['GET'])
def merged_pdf(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=False)

def jpg_to_pdf(jpg_files, output_pdf_path):
    pdf_canvas = canvas.Canvas(output_pdf_path, pagesize=A4)

    for jpg_file in jpg_files:
        if isinstance(jpg_file, str):  # If jpg_file is a file path
            image = Image.open(jpg_file)
        else:  # If jpg_file is a file object
            image = Image.open(jpg_file)

        image_width, image_height = image.size
        aspect_ratio = image_width / image_height
        pdf_width, pdf_height = A4

        if aspect_ratio > 1:
            pdf_canvas.setPageSize((pdf_width, pdf_width / aspect_ratio))
        else:
            pdf_canvas.setPageSize((pdf_height * aspect_ratio, pdf_height))

        if isinstance(jpg_file, str):  # If jpg_file is a file path
            pdf_canvas.drawImage(jpg_file, 0, 0, width=pdf_width, height=pdf_height, preserveAspectRatio=True)
        else:  # If jpg_file is a file object
            pdf_canvas.drawImage(jpg_file, 0, 0, width=pdf_width, height=pdf_height, preserveAspectRatio=True)
            jpg_file.close()  # Close the file object after reading

        pdf_canvas.showPage()

    pdf_canvas.save()

@app.route('/convert', methods=['POST','GET'])
def convert_to_pdf():
    if request.method == "POST":
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files found'}), 400

        jpg_files = []
        for file in request.files.getlist('files[]'):
            # Save the uploaded JPG files to temporary files
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                file.save(temp_file)
                jpg_files.append(temp_file.name)

        output_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], 'converted.pdf')

        jpg_to_pdf(jpg_files, output_pdf_path)

        return jsonify({'message': 'JPG converted to PDF successfully', 'output_pdf': output_pdf_path})
    return render_template('jpgtopdf.html')

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
