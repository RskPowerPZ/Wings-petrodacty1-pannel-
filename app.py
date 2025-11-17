from flask import Flask, request, jsonify
import requests
import json
import time
import random
import binascii
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from byte import Encrypt_ID, encrypt_api
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import uid_generator_pb2
from AccountPersonalShow_pb2 import AccountPersonalShowInfo
from secret import key, iv

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

class FreeFireAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.mount('https://', requests.adapters.HTTPAdapter(
            pool_connections=20, 
            pool_maxsize=20,
            max_retries=2
        ))
    
    def get_token_file(self, region):
        region = region.upper()
        if region == "IND":
            return "token_ind.json"
        elif region in ["BR", "US", "SAC", "NA"]:
            return "token_br.json"
        else:
            return "token_bd.json"

    def load_tokens(self, filename):
        try:
            with open(filename, "r") as file:
                data = json.load(file)
            tokens = [item["token"] for item in data if item.get("token")]
            logger.info(f"Loaded {len(tokens)} tokens from {filename}")
            return tokens
        except Exception as e:
            logger.error(f"Error loading tokens from {filename}: {e}")
            return []

    def create_protobuf(self, akiru_, aditya):
        message = uid_generator_pb2.uid_generator()
        message.akiru_ = akiru_
        message.aditya = aditya
        return message.SerializeToString()

    def protobuf_to_hex(self, protobuf_data):
        return binascii.hexlify(protobuf_data).decode()

    def decode_hex(self, hex_string):
        byte_data = binascii.unhexlify(hex_string.replace(' ', ''))
        users = AccountPersonalShowInfo()
        users.ParseFromString(byte_data)
        return users

    def encrypt_aes(self, hex_data, key, iv):
        key = key.encode()[:16]
        iv = iv.encode()[:16]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_data = pad(bytes.fromhex(hex_data), AES.block_size)
        encrypted_data = cipher.encrypt(padded_data)
        return binascii.hexlify(encrypted_data).decode()

    def fetch_player_info(self, uid, region, tokens, api):
        if not tokens:
            return None

        for token in random.sample(tokens, min(3, len(tokens))):
            try:
                saturn_ = int(uid)
            except ValueError:
                continue

            protobuf_data = self.create_protobuf(saturn_, 1)
            hex_data = self.protobuf_to_hex(protobuf_data)
            encrypted_hex = self.encrypt_aes(hex_data, key, iv)

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
                response = self.session.post(
                    f"{api}/GetPlayerPersonalShow", 
                    headers=headers, 
                    data=bytes.fromhex(encrypted_hex), 
                    timeout=10
                )
                
                if response.status_code == 200:
                    hex_response = response.content.hex()
                    account_info = self.decode_hex(hex_response)
                    
                    if account_info.HasField("basic_info"):
                        basic_info = account_info.basic_info
                        return {
                            "nickname": basic_info.nickname,
                            "level": basic_info.level,
                            "liked": basic_info.liked
                        }
                    
            except Exception as e:
                continue
        
        return None

    def send_friend_request_with_delay(self, uid, token, api, success_counter):
        """Send friend request with delay after every 50 successes"""
        try:
            encrypted_id = Encrypt_ID(uid)
            payload = f"08a7c4839f1e10{encrypted_id}1801"
            encrypted_payload = encrypt_api(payload)

            host = api.split("://")[1].split("/")[0]

            user_agents = [
                "Dalvik/2.1.0 (Linux; U; Android 9; SM-N975F Build/PI)",
                "Dalvik/2.1.0 (Linux; U; Android 10; SM-G981B Build/QP1A.190711.020)",
                "Dalvik/2.1.0 (Linux; U; Android 11; Pixel 5 Build/RQ3A.210805.001.A1)",
                "Dalvik/2.1.0 (Linux; U; Android 12; SM-S908E Build/SP1A.210812.016)"
            ]

            headers = {
                "Expect": "100-continue",
                "Authorization": f"Bearer {token}",
                "X-Unity-Version": "2018.4.11f1",
                "X-GA": "v1 1",
                "ReleaseVersion": "OB51",
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": str(len(encrypted_payload) // 2),
                "User-Agent": random.choice(user_agents),
                "Host": host,
                "Connection": "Keep-Alive",
                "Accept-Encoding": "gzip, deflate"
            }

            # Normal delay between requests
            time.sleep(random.uniform(0.1, 0.3))
            
            response = self.session.post(
                f"{api}/RequestAddingFriend",
                headers=headers, 
                data=bytes.fromhex(encrypted_payload), 
                timeout=15
            )

            if response.status_code == 200:
                # Increment success counter
                current_success = success_counter["count"] + 1
                success_counter["count"] = current_success
                
                logger.info(f"✅ Success #{current_success} - Token: {token[:12]}...")
                
                # Check if we need to wait after 50 successes
                if current_success % 50 == 0:
                    logger.info(f"⏳ 50 successful requests reached. Waiting 8 seconds...")
                    time.sleep(8)  # 8 second wait
                    logger.info("🚀 Resuming requests after 8 second wait")
                
                return "success"
            else:
                logger.warning(f"❌ HTTP {response.status_code} - Token: {token[:12]}...")
                return "failed"

        except requests.exceptions.Timeout:
            logger.warning(f"⏰ Timeout - Token: {token[:12]}...")
            return "failed"
        except requests.exceptions.ConnectionError:
            logger.warning(f"🔌 Connection Error - Token: {token[:12]}...")
            return "failed"
        except Exception as e:
            logger.warning(f"⚠️ Exception: {str(e)[:30]} - Token: {token[:12]}...")
            return "failed"

# Initialize API handler
api_handler = FreeFireAPI()

@app.route("/send_requests", methods=["GET"])
def send_requests():
    start_time = time.time()
    
    uid = request.args.get("uid")
    region = request.args.get("region", "").upper()
    target_count = int(request.args.get("count", 100))

    if not uid or not region:
        return jsonify({
            "status": "error",
            "message": "uid and region parameters are required"
        }), 400

    if region not in region_to_endpoint:
        return jsonify({
            "status": "error", 
            "message": "Unsupported region"
        }), 400

    token_filename = api_handler.get_token_file(region)
    all_tokens = api_handler.load_tokens(token_filename)
    
    if not all_tokens:
        return jsonify({
            "status": "error",
            "message": f"No tokens found in {token_filename}"
        }), 500

    if len(all_tokens) < target_count:
        return jsonify({
            "status": "error",
            "message": f"Not enough tokens. Need {target_count}, have {len(all_tokens)}"
        }), 400

    api = region_to_endpoint[region]

    # Fetch player info
    player_info = api_handler.fetch_player_info(uid, region, all_tokens, api)
    if not player_info:
        return jsonify({
            "status": "error",
            "message": "Failed to fetch player info - player may not exist"
        }), 500

    logger.info(f"🎯 Starting {target_count} friend requests to {player_info['nickname']} (Level {player_info['level']})")

    # Use all tokens
    tokens_to_use = all_tokens[:target_count]
    
    # Track success count for delays
    success_counter = {"count": 0}
    success_count = 0
    failed_count = 0

    # Conservative concurrency
    max_workers = min(8, target_count)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_token = {
            executor.submit(api_handler.send_friend_request_with_delay, uid, token, api, success_counter): token 
            for token in tokens_to_use
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_token):
            result = future.result()
            completed += 1
            
            if result == "success":
                success_count += 1
            else:
                failed_count += 1
            
            # Progress logging every 10 requests
            if completed % 10 == 0:
                elapsed = time.time() - start_time
                logger.info(f"📊 Progress: {completed}/{target_count} | ✅ {success_count} | ❌ {failed_count} | ⏱ {elapsed:.1f}s")

    total_time = time.time() - start_time

    # Clean JSON response
    response_data = {
        "status": "success",
        "player_info": {
            "nickname": player_info["nickname"],
            "level": player_info["level"],
            "likes": player_info["liked"]
        },
        "requests": {
            "successful": success_count,
            "failed": failed_count,
            "total": target_count
        },
        "time_taken": f"{total_time:.2f}s"
    }

    # Final performance log
    success_rate = (success_count / target_count) * 100
    if success_rate >= 95:
        logger.info(f"🎉 EXCELLENT: {success_count}/{target_count} successful ({success_rate:.1f}%) in {total_time:.2f}s")
    elif success_rate >= 80:
        logger.info(f"👍 GREAT: {success_count}/{target_count} successful ({success_rate:.1f}%) in {total_time:.2f}s")
    elif success_rate >= 60:
        logger.info(f"✅ GOOD: {success_count}/{target_count} successful ({success_rate:.1f}%) in {total_time:.2f}s")
    else:
        logger.warning(f"⚠️ NEEDS IMPROVEMENT: {success_count}/{target_count} successful ({success_rate:.1f}%) in {total_time:.2f}s")

    return jsonify(response_data)

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})

@app.route("/token_status", methods=["GET"])
def token_status():
    region = request.args.get("region", "IND").upper()
    token_filename = api_handler.get_token_file(region)
    tokens = api_handler.load_tokens(token_filename)
    
    return jsonify({
        "region": region,
        "total_tokens": len(tokens),
        "status": "active"
    })

if __name__ == "__main__":
    logger.info("🚀 Starting FreeFire Friend Request System with 50-request delays...")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)