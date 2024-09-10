from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'X-Requested-With': 'XMLHttpRequest',
}

LOGIN_DATA = {
    'LOGON_NAME': 'tc31Chittagong',
    'LOGON_PASS': 'tc31',
}

PREVIEW_URL = 'https://secure.incometax.gov.bd/Preview'
VIEW_CERTIFICATE_URL = 'https://secure.incometax.gov.bd/ViewCertiifcate'
LOGIN_URL = 'https://secure.incometax.gov.bd/Registration/Login'


def fetch_image_as_base64(image_url):
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        base64_encoded_image = base64.b64encode(response.content).decode('utf-8')
        return f"data:image/png;base64,{base64_encoded_image}"
    except requests.RequestException as e:
        app.logger.error(f"Failed to fetch image: {e}")
        return None


@app.route('/check-json')
def check_json():
    return jsonify({"status": "success", "message": "Flask app is running!"})


@app.route('/get_certificate', methods=['POST'])
def fetch_data():
    data = request.json

    # Extract data from the request
    OLD_TIN = data.get('OLD_TIN', '')
    NEW_TIN = data.get('NEW_TIN', '')
    NID = data.get('NID', '')
    PASSPORT_NUMBER = data.get('PASSPORT_NUMBER', '')
    CONTACT_TELEPHONE = data.get('CONTACT_TELEPHONE', '')
    CONTACT_EMAIL_ADDR = data.get('CONTACT_EMAIL_ADDR', '')

    # Check if all fields are empty
    if not any([OLD_TIN, NEW_TIN, NID, PASSPORT_NUMBER, CONTACT_TELEPHONE, CONTACT_EMAIL_ADDR]):
        return jsonify({'error': 'No data provided'}), 400

    session = requests.Session()
    
    # Login to the system
    try:
        session.post(LOGIN_URL, headers=COMMON_HEADERS, data=LOGIN_DATA)
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to log in', 'details': str(e)}), 500

    # Request preview data
    preview_data = {
        'TOKEN_ISSUED': '',
        'OLD_TIN': OLD_TIN,
        'NEW_TIN': NEW_TIN,
        'NID': NID,
        'PASSPORT_NUMBER': PASSPORT_NUMBER,
        'CONTACT_TELEPHONE': CONTACT_TELEPHONE,
        'CONTACT_EMAIL_ADDR': CONTACT_EMAIL_ADDR,
        'REG_TYPE_NO': '-1',
        'PAGE_NUM': '1',
    }

    try:
        preview_response = session.post(PREVIEW_URL, headers=COMMON_HEADERS, data=preview_data)
        preview_response.raise_for_status()
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to fetch preview data', 'details': str(e)}), 500

    preview_soup = BeautifulSoup(preview_response.text, 'html.parser')

    # Extract TIN value
    tin_value = None
    table = preview_soup.find('table', class_='table-bordered')
    if table:
        rows = table.find_all('tr')
        if len(rows) > 2:
            columns = rows[2].find_all('td')
            if len(columns) > 2:
                tin_value = columns[2].text.strip()

    if not tin_value:
        return jsonify({'error': 'TIN not found'}), 400

    # Request review data
    review_data = {'NEW_TIN': tin_value}
    review_headers = {'Content-Type': 'application/x-www-form-urlencoded', **COMMON_HEADERS}

    try:
        review_response = session.post(VIEW_CERTIFICATE_URL, headers=review_headers, data=review_data)
        review_response.raise_for_status()
    except requests.RequestException as e:
        return jsonify({'error': 'Failed to fetch review data', 'details': str(e)}), 500

    review_soup = BeautifulSoup(review_response.text, 'html.parser')

    # Extract credentials
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

    # Extract QR code image URL
    qr_img = review_soup.find('img', alt="QR Code")
    if qr_img:
        qr_code_url = qr_img['src']
        if qr_code_url:
            credentials['qr_code'] = qr_code_url

    # Extract Deputy Commissioner information
    deputy_commissioner_info = review_soup.find('span', style="text-align: left; font-size: x-small;")
    if deputy_commissioner_info:
        lines = [line.strip() for line in deputy_commissioner_info.get_text(separator="\n").split('\n') if line.strip()]

        if len(lines) > 1 and lines[0] == 'Deputy Commissioner' and lines[1] == 'of Taxes':
            lines[0] = f"{lines[0]} {lines[1]}"
            lines.pop(1)

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
