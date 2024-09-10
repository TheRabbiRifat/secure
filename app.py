from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import base64
from io import BytesIO

app = Flask(__name__)

def encode_image_to_base64(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image_data = BytesIO(response.content)
        base64_encoded_image = base64.b64encode(image_data.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{base64_encoded_image}"
    except requests.RequestException as e:
        app.logger.error(f"Failed to fetch image: {e}")
        return None

@app.route('/check-json')
def check_json():
    return jsonify({"status": "success", "message": "Flask Tin app is running!"})



@app.route('/get_certificate', methods=['POST'])
def fetch_data():
    data = request.json

    OLD_TIN = data.get('OLD_TIN', '')
    NEW_TIN = data.get('NEW_TIN', '')
    NID = data.get('NID', '')
    PASSPORT_NUMBER = data.get('PASSPORT_NUMBER', '')
    CONTACT_TELEPHONE = data.get('CONTACT_TELEPHONE', '')
    CONTACT_EMAIL_ADDR = data.get('CONTACT_EMAIL_ADDR', '')

    # Check if all fields are empty
    if not any([OLD_TIN, NEW_TIN, NID, PASSPORT_NUMBER, CONTACT_TELEPHONE, CONTACT_EMAIL_ADDR]):
        return jsonify({'error': 'No data provided'}), 400

    common_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'X-Requested-With': 'XMLHttpRequest',
    }

    session = requests.Session()
    login_data = {
        'LOGON_NAME': 'tc31Chittagong',
        'LOGON_PASS': 'tc31',
    }
    session.post('https://secure.incometax.gov.bd/Registration/Login', headers=common_headers, data=login_data)

    preview_data = {
        'TOKEN_ISSUED': '',
        'OLD_TIN': OLD_TIN,
        'NEW_TIN': NEW_TIN,
        'NID': NID,
        'DOB_DAY': '',
        'DOB_MONTH': '',
        'DOB_YEAR': '',
        'PASSPORT_NUMBER': PASSPORT_NUMBER,
        'ASSES_NAME': '',
        'CONTACT_TELEPHONE': CONTACT_TELEPHONE,
        'CONTACT_EMAIL_ADDR': CONTACT_EMAIL_ADDR,
        'REG_TYPE_NO': '-1',
        'IS_OLD_TIN': '',
        'FATH_NAME': '',
        'ZONE_NO': '-1',
        'CIRCLE_NO': '-1',
        'DT_APP_FROM_DAY': '',
        'DT_APP_FROM_MONTH': '',
        'DT_APP_FROM_YEAR': '',
        'DT_APP_TO_DAY': '',
        'DT_APP_TO_MONTH': '',
        'DT_APP_TO_YEAR': '',
        'PAGE_NUM': '1',
    }

    try:
        preview_response = session.post('https://secure.incometax.gov.bd/Preview', headers=common_headers, data=preview_data)
        preview_response.raise_for_status()
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to fetch preview data', 'details': str(e)}), 500

    preview_soup = BeautifulSoup(preview_response.text, 'html.parser')

    tin_value = None
    table = preview_soup.find('table', class_='table-bordered')
    if table:
        rows = table.find_all('tr')
        if len(rows) > 2:
            third_row = rows[2]
            columns = third_row.find_all('td')
            if len(columns) > 2:
                tin_value = columns[2].text.strip()

    if not tin_value:
        return jsonify({'error': 'TIN not found'}), 400

    review_headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        **common_headers
    }
    review_data = {'NEW_TIN': tin_value}

    try:
        review_response = session.post('https://secure.incometax.gov.bd/ViewCertiifcate', headers=review_headers, data=review_data)
        review_response.raise_for_status()
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to fetch review data', 'details': str(e)}), 500

    review_soup = BeautifulSoup(review_response.text, 'html.parser')

    credentials = {'TIN': tin_value}
    field_map = {
        'name': "Name :",
        'father_name': "Father's Name :",
        'mother_name': "Mother's Name :",
        'current_address': "Current Address :",
        'permanent_address': "Permanent Address :",
        'previous_tin': "Previous TIN :",
        'status': "Status :",
        'date': "Date :",
        'last_update': "Last Update :"
    }

    for label, field_text in field_map.items():
        result = review_soup.find(string=lambda x: x and field_text in x)
        if result:
            parent = result.parent
            value = parent.find('span').text.strip() if parent.find('span') else result.split(field_text)[1].strip()
            credentials[label] = value
        else:
            credentials[label] = ""

    qr_img = review_soup.find('img', alt="QR Code")
    if qr_img:
        base64_qr_code = encode_image_to_base64(qr_img['src'])
        if base64_qr_code:
            credentials['qr_code'] = base64_qr_code

    deputy_commissioner_info = review_soup.find('span', style="text-align: left; font-size: x-small;")
    if deputy_commissioner_info:
        text = deputy_commissioner_info.get_text(separator="\n").strip()
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        if len(lines) > 1 and lines[0] == 'Deputy Commissioner' and lines[1] == 'of Taxes':
            lines[0] = f"{lines[0]} {lines[1]}"
            del lines[1]

        if len(lines) >= 5:
            credentials['office_name'] = lines[0].strip()
            credentials['office_circle'] = lines[1].strip()
            credentials['office_zone'] = lines[2].strip()

            address_line = lines[3]
            if 'Address :' in address_line:
                credentials['office_address'] = address_line.split('Address :')[1].strip()

            phone_line = lines[4]
            if 'Phone :' in phone_line:
                credentials['office_phone'] = phone_line.split('Phone :')[1].strip()

    return jsonify(credentials)

@app.route('/check-system-status', methods=['GET'])
def check_system_status():
    user_agent = request.headers.get('User-Agent')

    # Check if the User-Agent matches the specified value
    if user_agent == 'Puffinx64, MacBook':
        return jsonify({
            'status': 'ok',
            'message': 'System Working properly'
        }), 200
    else:
        return jsonify({'error': 'Unauthorized User-Agent'}), 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)  # Use debug mode for development
