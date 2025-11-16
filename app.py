from flask import Flask, request, jsonify
import requests
import json
import threading
import time
import random
import binascii
from byte import Encrypt_ID, encrypt_api
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import uid_generator_pb2
from AccountPersonalShow_pb2 import AccountPersonalShowInfo
from secret import key, iv

app = Flask(__name__)

region_to_endpoint = {
    "IND": "https://client.ind.freefiremobile.com",
    "BR": "https://client.us.freefiremobile.com",
    "US": "https://client.us.freefiremobile.com",
    "SAC": "https://client.us.freefiremobile.com",
    "NA": "https://client.us.freefiremobile.com",
    "EU": "https://clientbp.ggblueshark.com",
    "ME": "https://clientbp.ggblueshark.com",
    "ID": "https://clientbp.ggblueshark.com",
    "TH": "https://clientbp.ggblueshark.com",
    "VN": "https://clientbp.ggblueshark.com",
    "SG": "https://clientbp.ggblueshark.com",
    "BD": "https://clientbp.ggblueshark.com",
    "PK": "https://clientbp.ggblueshark.com",
    "MY": "https://clientbp.ggblueshark.com",
    "PH": "https://clientbp.ggblueshark.com",
    "RU": "https://clientbp.ggblueshark.com",
    "AFR": "https://clientbp.ggblueshark.com",
}

def get_token_file(region):
    region = region.upper()
    if region == "IND":
        return "token_ind.json"
    elif region in ["BR", "US", "SAC", "NA"]:
        return "token_br.json"
    else:
        return "token_bd.json"

def load_tokens(filename):
    try:
        with open(filename, "r") as file:
            data = json.load(file)
        tokens = [item["token"] for item in data]
        return tokens
    except Exception as e:
        print(f"Error loading tokens from {filename}: {e}")
        return []

def create_protobuf(akiru_, aditya):
    message = uid_generator_pb2.uid_generator()
    message.akiru_ = akiru_
    message.aditya = aditya
    return message.SerializeToString()

def protobuf_to_hex(protobuf_data):
    return binascii.hexlify(protobuf_data).decode()

def decode_hex(hex_string):
    byte_data = binascii.unhexlify(hex_string.replace(' ', ''))
    users = AccountPersonalShowInfo()
    users.ParseFromString(byte_data)
    return users

def encrypt_aes(hex_data, key, iv):
    key = key.encode()[:16]
    iv = iv.encode()[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
    encrypted_data = cipher.encrypt(padded_data)
    return binascii.hexlify(encrypted_data).decode()

def fetch_player_info(uid, region, tokens, api):
    if not tokens:
        return None

    token = random.choice(tokens)
    try:
        saturn_ = int(uid)
    except ValueError:
        return None

    protobuf_data = create_protobuf(saturn_, 1)
    hex_data = protobuf_to_hex(protobuf_data)
    encrypted_hex = encrypt_aes(hex_data, key, iv)

    host = api.split("://")[1].split("/")[0]

    headers = {
        'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)',
        'Connection': 'Keep-Alive',
        'Expect': '100-continue',
        'Authorization': f'Bearer {token}',
        'X-Unity-Version': '2018.4.11f1',
        'X-GA': 'v1 1',
        'ReleaseVersion': 'OB51',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Host': host,
    }

    try:
        response = requests.post(f"{api}/GetPlayerPersonalShow", headers=headers, data=bytes.fromhex(encrypted_hex), timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    hex_response = response.content.hex()

    try:
        account_info = decode_hex(hex_response)
    except Exception:
        return None

    if account_info.HasField("basic_info"):
        basic_info = account_info.basic_info
        return {
            "nickname": basic_info.nickname,
            "level": basic_info.level,
            "liked": basic_info.liked
        }
    return None

def send_friend_request(uid, token, results, lock, api):
    encrypted_id = Encrypt_ID(uid)
    payload = f"08a7c4839f1e10{encrypted_id}1801"
    encrypted_payload = encrypt_api(payload)

    host = api.split("://")[1].split("/")[0]

    url = f"{api}/RequestAddingFriend"
    headers = {
        "Expect": "100-continue",
        "Authorization": f"Bearer {token}",
        "X-Unity-Version": "2018.4.11f1",
        "X-GA": "v1 1",
        "ReleaseVersion": "OB51",
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": "16",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; SM-N975F Build/PI)",
        "Host": host,
        "Connection": "close",
        "Accept-Encoding": "gzip, deflate, br"
    }

    try:
        response = requests.post(url, headers=headers, data=bytes.fromhex(encrypted_payload), timeout=10)
        with lock:
            if response.status_code == 200:
                results["success"] += 1
                print(f"✅ Success #{results['success']}")
            else:
                results["failed"] += 1
    except Exception as e:
        print(f"Error in request: {e}")
        with lock:
            results["failed"] += 1

@app.route("/send_requests", methods=["GET"])
def send_requests():
    uid = request.args.get("uid")
    region = request.args.get("region", "").upper()

    if not uid or not region:
        return jsonify({"error": "uid and region parameters are required"}), 400

    if region not in region_to_endpoint:
        return jsonify({"error": "Unsupported region"}), 400

    token_filename = get_token_file(region)
    tokens = load_tokens(token_filename)
    if not tokens:
        return jsonify({"error": f"No tokens found in {token_filename}"}), 500

    api = region_to_endpoint[region]

    # Fetch player info first
    player_info = fetch_player_info(uid, region, tokens, api)
    if not player_info:
        return jsonify({"error": "Failed to fetch player info"}), 500

    results = {"success": 0, "failed": 0}
    MAX_SUCCESS = 120
    BATCH_SIZE = 50
    DELAY = 0.3
    lock = threading.Lock()

    def start_batch(batch_tokens):
        batch_threads = []
        for token in batch_tokens:
            with lock:
                if results["success"] >= MAX_SUCCESS:
                    print(f"Reached {MAX_SUCCESS} successes. Stopping further requests.")
                    return False
            thread = threading.Thread(target=send_friend_request, args=(uid, token, results, lock, api))
            batch_threads.append(thread)
            thread.start()
            time.sleep(DELAY)

        for thread in batch_threads:
            thread.join()
        return True

    batch_num = 1
    for i in range(0, len(tokens), BATCH_SIZE):
        if results["success"] >= MAX_SUCCESS:
            break
        batch_tokens = tokens[i:i + BATCH_SIZE]
        if not batch_tokens:
            break
        print(f"Starting batch {batch_num} (requests {i+1} to {min(i + BATCH_SIZE, len(tokens))})")
        continue_batch = start_batch(batch_tokens)
        if not continue_batch:
            break
        print(f"Batch {batch_num} completed. Success so far: {results['success']}")
        if results["success"] >= MAX_SUCCESS:
            break
        batch_num += 1

    total_requests = results["success"] + results["failed"]
    status = 1 if results["success"] > 0 else 2

    response_data = {
        "nickname": player_info["nickname"],
        "level": player_info["level"],
        "likes": player_info["liked"],
        "success_count": results["success"],
        "failed_count": results["failed"],
        "total_requests": total_requests,
        "status": status
    }

    return jsonify(response_data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)