import re
import requests
import hashlib
import platform
import uuid
import sys
import os
import time
from datetime import datetime
from Crypto.Cipher import AES
from cryptography.fernet import Fernet
import webbrowser
from dotenv import load_dotenv, set_key
import json

load_dotenv()

class KeyAuth:
    def __init__(self, name=None, ownerid=None, secret=None, version=None, config_file="auth_config.json"):
        # Load configuration
        self.config_file = config_file
        self.load_config()
        
        # Override with direct parameters if provided
        if name: self.name = name
        if ownerid: self.ownerid = ownerid
        if secret: self.secret = secret
        if version: self.version = version
        
        self.sessionid = ""
        self.initialized = False
        self.username = None
        self.logged_in = False
        
        # Initialize connection
        print("\n[System] Initializing connection...")
        self.base_url = self.solve_js_challenge_and_get_url()
        if not self.base_url:
            self.show_maintenance()
            sys.exit(1)
            
        self.api_endpoint = f"{self.base_url}/api/1.2/"
        print(f"[System] Connected to: {self.base_url}")

        # Encryption setup
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            self.encryption_key = Fernet.generate_key().decode()
            env_path = os.path.join(os.getcwd(), '.env')
            set_key(env_path, "ENCRYPTION_KEY", self.encryption_key)
            print("[Security] Generated new encryption key")

        self.fernet = Fernet(self.encryption_key.encode())

    def load_config(self):
        """Load authentication configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                self.name = config.get('name')
                self.ownerid = config.get('ownerid')
                self.secret = config.get('secret')
                self.version = config.get('version', '1.0')
        except FileNotFoundError:
            raise Exception(f"Configuration file '{self.config_file}' not found. Please create it with your auth details.")
        except json.JSONDecodeError:
            raise Exception(f"Invalid JSON format in '{self.config_file}'")

    def save_config(self, name, ownerid, secret, version):
        """Save authentication configuration to JSON file"""
        config = {
            'name': name,
            'ownerid': ownerid,
            'secret': secret,
            'version': version
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)

    def to_bytes(self, hex_str):
        return bytes.fromhex(hex_str)

    def decrypt_js_aes(self, c_hex, key_hex, iv_hex):
        c = self.to_bytes(c_hex)
        key = self.to_bytes(key_hex)
        iv = self.to_bytes(iv_hex)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.decrypt(c).hex()

    def extract_js_aes_vars(self, html):
        match = re.search(r'toNumbers\("([a-f0-9]{32})"\).*?toNumbers\("([a-f0-9]{32})"\).*?toNumbers\("([a-f0-9]{32})"\)', html, re.DOTALL)
        if not match:
            raise ValueError("AES variables not found in page.")
        return match.groups()

    def solve_js_challenge_and_get_url(self):
        session = requests.Session()
        headers = {
            "User-Agent": "KeyAuth Python Client",
            "Accept": "text/plain"
        }

        try:
            # First request to get the challenge
            print("[Challenge] Solving JavaScript challenge...")
            r = session.get("http://www.keyauthpanel.thsite.top/urlshow.php", headers=headers)
            
            # Extract and decrypt the cookie
            key_hex, iv_hex, enc_hex = self.extract_js_aes_vars(r.text)
            cookie_val = self.decrypt_js_aes(enc_hex, key_hex, iv_hex)
            
            # Second request with the solved cookie
            session.cookies.set("__test", cookie_val)
            r2 = session.get("http://www.keyauthpanel.thsite.top/urlshow.php?i=1", headers=headers)

            # Handle potential second challenge
            if "<script>" in r2.text:
                print("[Challenge] Solving second challenge...")
                key_hex, iv_hex, enc_hex = self.extract_js_aes_vars(r2.text)
                cookie_val = self.decrypt_js_aes(enc_hex, key_hex, iv_hex)
                session.cookies.set("__test", cookie_val)
                r2 = session.get("http://www.keyauthpanel.thsite.top/urlshow.php?i=2", headers=headers)

            final_url = r2.text.strip()
            
            # Validate the URL
            if not final_url.startswith(('http://', 'https://')):
                if final_url.startswith("ERROR_"):
                    raise ValueError(f"Server error: {final_url[6:]}")
                raise ValueError("Invalid URL format received")
                
            print(f"[Success] Retrieved URL: {final_url}")
            return final_url.rstrip('/')
            
        except Exception as e:
            print(f"[Challenge Error] Failed to solve challenge: {str(e)}")
            return None

    def show_maintenance(self):
        print("\n[System Notice] Service Temporarily Unavailable")
        print("We're unable to connect to the authentication service.")
        print("Possible reasons:")
        print("- Service is undergoing maintenance")
        print("- Network connectivity issues")
        print("- Server configuration changed")
        print("\nPlease try again later or contact support.")
        sys.exit(0)

    def init(self):
        if self.initialized:
            return True

        data = {
            "type": "init",
            "name": self.name,
            "ownerid": self.ownerid,
            "ver": self.version
        }

        try:
            print("[API] Initializing session...")
            response = self.__request(data, first_call=True)
            if response["success"]:
                self.sessionid = response["sessionid"]
                self.initialized = True
                print("[API] Session initialized successfully")
                return True
            else:
                error_msg = response.get('message', 'Unknown error')
                print(f"[API Error] {error_msg}")
                return False
        except Exception as e:
            print(f"[Error] Initialization failed: {str(e)}")
            return False

    def login(self, username, password):
        if not self.initialized and not self.init():
            return False, "System not initialized"

        hwid = self.__get_hwid()

        # First try with direct password
        success, message = self._attempt_login(username, password, hwid)
        if success:
            self.username = username
            self.logged_in = True
            return True, message
        
        # If failed, try with encrypted password
        encrypted_password = self.encrypt_password(password)
        success, message = self._attempt_login(username, encrypted_password, hwid)
        if success:
            self.username = username
            self.logged_in = True
        return success, message

    def _attempt_login(self, username, password, hwid):
        data = {
            "type": "login",
            "username": username,
            "pass": password,
            "hwid": hwid,
            "sessionid": self.sessionid,
            "name": self.name,
            "ownerid": self.ownerid
        }

        try:
            response = self.__request(data)
            if response.get("success"):
                print(f"\n[Success] Welcome back, {username}!")
                print(f"IP: {self.get_ip_address()}")
                print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                return True, response.get("message", "Login successful")
            else:
                return False, response.get("message", "Unknown error")
        except Exception as e:
            return False, f"Login error: {str(e)}"

    def register_with_license(self, license_key, username=None, password=None):
        if not self.initialized and not self.init():
            return False, "System not initialized"

        hwid = self.__get_hwid()

        data = {
            "type": "license",
            "key": license_key,
            "hwid": hwid,
            "sessionid": self.sessionid,
            "name": self.name,
            "ownerid": self.ownerid
        }

        try:
            response = self.__request(data)
            if not response.get("success"):
                return False, f"License Error: {response.get('message', 'Invalid license')}"

            if username is None or password is None:
                print("\n[Success] License validated! Please create your account:")
                username = input("Username: ").strip()
                password = input("Password: ").strip()

                if not username or not password:
                    return False, "Username and password required"

            register_data = {
                "type": "register",
                "username": username,
                "pass": self.encrypt_password(password),
                "hwid": hwid,
                "sessionid": self.sessionid,
                "name": self.name,
                "ownerid": self.ownerid
            }

            reg_response = self.__request(register_data)
            if reg_response.get("success"):
                self.username = username
                self.logged_in = True
                return True, "Account created successfully!"
            else:
                return False, reg_response.get("message", "Registration failed")

        except Exception as e:
            return False, f"Registration error: {str(e)}"

    def check_license_validity(self, license_key):
        if not self.initialized and not self.init():
            return False, "System not initialized"

        hwid = self.__get_hwid()

        data = {
            "type": "license",
            "key": license_key,
            "hwid": hwid,
            "sessionid": self.sessionid,
            "name": self.name,
            "ownerid": self.ownerid
        }

        try:
            response = self.__request(data)
            if response.get("success"):
                return True, "Valid license key!"
            else:
                return False, response.get("message", "Invalid license key")
        except Exception as e:
            return False, f"License check error: {str(e)}"

    def __request(self, data, first_call=False):
        if not first_call:
            data["enckey"] = self.__get_encryption_key()

        try:
            response = requests.post(
                self.api_endpoint,
                data=data,
                timeout=10,
                headers={
                    'User-Agent': 'KeyAuth Python Client',
                    'Connection': 'keep-alive'
                }
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"\n[API Error] Failed to connect to authentication server")
            self.show_maintenance()
        except ValueError:
            print("\n[API Error] Invalid server response")
            self.show_maintenance()

    def encrypt_password(self, password):
        try:
            return self.fernet.encrypt(password.encode()).decode()
        except Exception as e:
            raise Exception(f"Password encryption failed: {str(e)}")

    def __get_encryption_key(self):
        if not self.sessionid:
            raise Exception("Session ID not available")
        return hashlib.sha256((self.secret + self.sessionid + self.name + self.ownerid).encode()).hexdigest()

    def __get_hwid(self):
        hwid = str(platform.processor()) + str(uuid.getnode())
        return hashlib.sha256(hwid.encode()).hexdigest()

    def get_ip_address(self):
        try:
            response = requests.get("https://api.ipify.org?format=json", timeout=5)
            return response.json().get("ip", "Unknown")
        except requests.exceptions.RequestException:
            return "Unknown"

    def is_authenticated(self):
        return self.logged_in

    def get_username(self):
        return self.username if self.logged_in else None

    def logout(self):
        self.logged_in = False
        self.username = None
        return True, "Logged out successfully"


def run_standalone():
    # Create a sample config file if it doesn't exist
    config_file = "auth_config.json"
    if not os.path.exists(config_file):
        sample_config = {
            "name": "your_app_name",
            "ownerid": "your_owner_id",
            "secret": "your_secret_key",
            "version": "1.0"
        }
        with open(config_file, 'w') as f:
            json.dump(sample_config, f, indent=4)
        print(f"[Config] Created sample configuration file: {config_file}")
        print("Please edit it with your actual authentication details")
        return

    auth = KeyAuth(config_file=config_file)

    print("\n=== KeyAuth Authentication System ===")
    print("=== Secure Access Control ===")
    
    while True:
        print("\nMenu Options:")
        print("1. Register with License Key")
        print("2. Login with Credentials")
        print("3. Validate License Key")
        print("4. Update Authentication Config")
        print("Q. Quit Program")

        choice = input("\nSelect option: ").strip().lower()

        if choice == 'q':
            print("\nGoodbye!")
            sys.exit(0)

        elif choice == '1':
            license_key = input("Enter your license key: ").strip()
            if not license_key:
                print("[Error] License key required")
                continue
                
            success, message = auth.register_with_license(license_key)
            print(f"\n{'✅ Success' if success else '❌ Error'}: {message}")

        elif choice == '2':
            username = input("Username: ").strip()
            password = input("Password: ").strip()
            
            success, message = auth.login(username, password)
            print(f"\n{'✅ Success' if success else '❌ Error'}: {message}")

        elif choice == '3':
            license_key = input("Enter license key to validate: ").strip()
            if not license_key:
                print("[Error] License key required")
                continue
                
            success, message = auth.check_license_validity(license_key)
            print(f"\n{'✅ Valid' if success else '❌ Invalid'}: {message}")

        elif choice == '4':
            print("\nUpdate Authentication Configuration:")
            name = input("Application Name: ").strip()
            ownerid = input("Owner ID: ").strip()
            secret = input("Secret Key: ").strip()
            version = input("Version (default 1.0): ").strip() or "1.0"
            
            auth.save_config(name, ownerid, secret, version)
            print("✅ Configuration updated successfully!")
            
            # Reinitialize with new config
            auth = KeyAuth(config_file=config_file)

        else:
            print("[Error] Invalid selection")

if __name__ == "__main__":
    try:
        run_standalone()
    except KeyboardInterrupt:
        print("\nProgram interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n[Critical Error] {str(e)}")
        sys.exit(1)