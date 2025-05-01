from KeyAuth import KeyAuth
from datetime import datetime
import time
import sys

# Initialize the authentication system
auth = KeyAuth()  # Uses default credentials from the class

def display_menu():
    print("\n=== Authentication System ===")
    print("1. Login")
    print("2. Register with License")
    print("3. Validate License Key")
    print("4. Check Subscription")
    print("5. Logout")
    print("6. Exit")
    return input("Select an option: ").strip()

def login_flow(max_attempts=3):
    print("\n=== Login ===")
    attempts = 0
    
    while attempts < max_attempts:
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        
        success, message = auth.login(username, password)
        if success:
            print(f"\n✅ Welcome {auth.get_username()}!")
            print(f"IP Address: {auth.get_ip_address()}")
            print(f"Login Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return True
        else:
            attempts += 1
            remaining = max_attempts - attempts
            print(f"\n❌ Login failed: {message}")
            if remaining > 0:
                print(f"Attempts remaining: {remaining}")
            else:
                print("Maximum login attempts reached. Please try again later.")
                time.sleep(2)
                return False
    
    return False

def protected_function():
    """Example function that requires authentication"""
    print("\n=== Protected Content ===")
    print("This content is only available to authenticated users")
    print(f"Welcome, {auth.get_username()}!")
    # Add your protected functionality here
    input("\nPress Enter to return to menu...")

def register_flow():
    print("\n=== Register New Account ===")
    license_key = input("License Key: ").strip()
    
    # First validate license
    print("Validating license...")
    valid, msg = auth.check_license_validity(license_key)
    if not valid:
        print(f"\n❌ License Error: {msg}")
        return False
    
    # Get account details
    print("\nLicense valid! Create your account:")
    while True:
        username = input("Username: ").strip()
        if username:
            break
        print("❌ Username cannot be empty")
    
    while True:
        password = input("Password: ").strip()
        if len(password) >= 6:
            confirm = input("Confirm Password: ").strip()
            if password == confirm:
                break
            print("❌ Passwords don't match!")
        else:
            print("❌ Password must be at least 6 characters")
    
    # Register with license
    success, message = auth.register_with_license(license_key, username, password)
    if success:
        print(f"\n✅ Registration successful! Welcome {username}!")
        # Auto-login after registration
        if auth.login(username, password)[0]:
            protected_function()
        return True
    else:
        print(f"\n❌ Registration failed: {message}")
        return False

def validate_license_flow():
    print("\n=== Validate License ===")
    license_key = input("Enter license key: ").strip()
    if not license_key:
        print("❌ License key cannot be empty")
        return
        
    valid, msg = auth.check_license_validity(license_key)
    if valid:
        print(f"\n✅ Valid license: {msg}")
    else:
        print(f"\n❌ Invalid license: {msg}")

def check_subscription():
    if not auth.is_authenticated():
        print("\n❌ You need to login first")
        return
    
    print("\n=== Subscription Status ===")
    print(f"User: {auth.get_username()}")
    print("Plan: Premium")
    print("Expires: 2024-12-31")
    print("Status: Active")

def main():
    while True:
        choice = display_menu()
        
        if choice == "1":  # Login
            if auth.is_authenticated():
                print("\nℹ️ You're already logged in as", auth.get_username())
                protected_function()
            else:
                if login_flow():
                    protected_function()
            
        elif choice == "2":  # Register
            if auth.is_authenticated():
                print("\nℹ️ Please logout first to register a new account")
            else:
                register_flow()
            
        elif choice == "3":  # Validate License
            validate_license_flow()
            
        elif choice == "4":  # Check Subscription
            check_subscription()
            
        elif choice == "5":  # Logout
            if auth.is_authenticated():
                auth.logout()
                print("\n✅ Successfully logged out")
            else:
                print("\nℹ️ Not currently logged in")
                
        elif choice == "6":  # Exit
            print("\nGoodbye!")
            break
            
        else:
            print("\n❌ Invalid selection")
        
        # Small delay for better UX
        time.sleep(0.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProgram interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n⚠️ Critical Error: {str(e)}")
        sys.exit(1)