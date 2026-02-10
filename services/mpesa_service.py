"""
MPESA Daraja API Integration Service
Handles STK Push, C2B, and B2C transactions
"""

import os
import base64
import requests
from datetime import datetime
from extensions import db
from models import MpesaTransaction


class MpesaService:
    """Service class for MPESA Daraja API integration"""

    BASE_URL = "https://sandbox.safaricom.co.ke"  # Use sandbox for testing
    # For production: BASE_URL = 'https://api.safaricom.co.ke'

    def __init__(self):
        self.consumer_key = os.environ.get("MPESA_CONSUMER_KEY")
        self.consumer_secret = os.environ.get("MPESA_CONSUMER_SECRET")
        self.short_code = os.environ.get("MPESA_SHORTCODE")
        self.passkey = os.environ.get("MPESA_LIPA_NA_MPESA_PASSKEY")
        self.callback_url = os.environ.get("MPESA_CALLBACK_URL")

    def _get_access_token(self):
        """Get OAuth access token from MPESA API"""
        try:
            auth = base64.b64encode(
                f"{self.consumer_key}:{self.consumer_secret}".encode()
            ).decode()

            headers = {
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
            }

            response = requests.get(
                f"{self.BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                return response.json().get("access_token")
            return None
        except Exception as e:
            print(f"Error getting access token: {e}")
            return None

    def _generate_password(self):
        """Generate password for STK Push"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        data_to_encode = f"{self.short_code}{self.passkey}{timestamp}"
        return base64.b64encode(data_to_encode.encode()).decode(), timestamp

    def initiate_stk_push(
        self, phone_number, amount, order_id, description="Event Ticket"
    ):
        """Initiate STK Push request to customer's phone"""
        try:
            access_token = self._get_access_token()
            if not access_token:
                print("[MPESA] Failed to get access token - checking credentials")
                print(f"[MPESA] Consumer key set: {bool(self.consumer_key)}")
                print(f"[MPESA] Consumer secret set: {bool(self.consumer_secret)}")
                print(f"[MPESA] Shortcode set: {bool(self.short_code)}")
                print(f"[MPESA] Passkey set: {bool(self.passkey)}")
                print(f"[MPESA] Callback URL set: {bool(self.callback_url)}")
                return {"success": False, "error": "Failed to get access token"}

            password, timestamp = self._generate_password()

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            payload = {
                "BusinessShortCode": self.short_code,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": os.environ.get(
                    "MPESA_TRANSACTION_TYPE", "CustomerPayBillOnline"
                ),
                "Amount": int(amount),
                "PartyA": phone_number,
                "PartyB": self.short_code,
                "PhoneNumber": phone_number,
                "CallBackURL": self.callback_url,
                "AccountReference": order_id,
                "TransactionDesc": description,
            }

            print(f"[MPESA] Initiating STK push:")
            print(f"[MPESA] Phone: {phone_number}")
            print(f"[MPESA] Amount: {amount}")
            print(f"[MPESA] Order ID: {order_id}")
            print(f"[MPESA] Shortcode: {self.short_code}")

            response = requests.post(
                f"{self.BASE_URL}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers=headers,
                timeout=30,
            )

            print(f"[MPESA] Response status: {response.status_code}")
            print(f"[MPESA] Response body: {response.text}")

            if response.status_code == 200:
                result = response.json()
                if result.get("ResponseCode") == "0":
                    return {
                        "success": True,
                        "checkout_request_id": result.get("CheckoutRequestID"),
                        "merchant_request_id": result.get("MerchantRequestID"),
                        "message": result.get("ResponseDescription"),
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("ResponseDescription", "STK Push failed"),
                    }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                }
        except Exception as e:
            print(f"STK Push error: {e}")
            return {"success": False, "error": str(e)}

    def process_callback(self, callback_data):
        """Process MPESA callback response"""
        try:
            stk_callback = callback_data.get("Body", {}).get("stkCallback", {})

            result_code = stk_callback.get("ResultCode")
            result_desc = stk_callback.get("ResultDesc")
            checkout_request_id = stk_callback.get("CheckoutRequestID")

            # Find the transaction
            transaction = MpesaTransaction.query.filter_by(
                transaction_id=checkout_request_id
            ).first()

            if not transaction:
                return {"success": False, "error": "Transaction not found"}

            transaction.result_code = result_code
            transaction.result_desc = result_desc

            if result_code == 0:
                # Successful transaction
                callback_metadata = stk_callback.get("CallbackMetadata", {}).get(
                    "Item", []
                )

                for item in callback_metadata:
                    if item.get("Name") == "Amount":
                        transaction.amount = item.get("Value")
                    elif item.get("Name") == "MpesaReceiptNumber":
                        transaction.mpesa_receipt = item.get("Value")
                    elif item.get("Name") == "PhoneNumber":
                        transaction.phone_number = str(item.get("Value"))

                transaction.status = "COMPLETED"

                return {
                    "success": True,
                    "transaction": transaction.to_dict(),
                    "status": "COMPLETED",
                }
            else:
                # Failed transaction
                transaction.status = "FAILED"
                db.session.commit()
                return {"success": False, "error": result_desc, "status": "FAILED"}

        except Exception as e:
            print(f"Callback processing error: {e}")
            return {"success": False, "error": str(e)}

    def query_stk_status(self, checkout_request_id):
        """Query the status of an STK Push transaction"""
        try:
            access_token = self._get_access_token()
            if not access_token:
                return {"success": False, "error": "Failed to get access token"}

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            payload = {
                "BusinessShortCode": self.short_code,
                "CheckoutRequestID": checkout_request_id,
            }

            response = requests.post(
                f"{self.BASE_URL}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("ResponseCode") == "0":
                    return {
                        "success": True,
                        "ResultCode": 0,
                        "ResultDesc": result.get("ResponseDescription"),
                    }
                else:
                    return {
                        "success": False,
                        "ResultCode": result.get("ResponseCode"),
                        "ResultDesc": result.get("ResponseDescription", "STK Query failed"),
                    }
            else:
                return {
                    "success": False,
                    "ResultCode": -1,
                    "ResultDesc": f"HTTP {response.status_code}: {response.text}",
                }
        except Exception as e:
            print(f"STK Query error: {e}")
            return {"success": False, "ResultCode": -1, "ResultDesc": str(e)}

    def register_urls(self):
        """Register C2B validation and confirmation URLs"""
        try:
            access_token = self._get_access_token()
            if not access_token:
                return {"success": False, "error": "Failed to get access token"}

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            payload = {
                "ShortCode": self.short_code,
                "ResponseType": "Completed",
                "ConfirmationURL": os.environ.get("MPESA_CONFIRMATION_URL"),
                "ValidationURL": os.environ.get("MPESA_VALIDATION_URL"),
            }

            response = requests.post(
                f"{self.BASE_URL}/mpesa/c2b/v1/registerurl",
                json=payload,
                headers=headers,
                timeout=30,
            )

            return response.json()
        except Exception as e:
            print(f"URL registration error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
mpesa_service = MpesaService()
