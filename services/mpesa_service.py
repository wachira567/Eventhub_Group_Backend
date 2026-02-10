import os
import base64
import requests
from datetime import datetime
from extensions import db
from models import MpesaTransaction

class MpesaService:
    BASE_URL = "https://sandbox.safaricom.co.ke"

    def __init__(self):
        self.consumer_key = os.environ.get("MPESA_CONSUMER_KEY")
        self.consumer_secret = os.environ.get("MPESA_CONSUMER_SECRET")
        self.short_code = os.environ.get("MPESA_SHORTCODE")
        self.passkey = os.environ.get("MPESA_LIPA_NA_MPESA_PASSKEY")
        self.callback_url = os.environ.get("MPESA_CALLBACK_URL")

    def _get_access_token(self):
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
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        data_to_encode = f"{self.short_code}{self.passkey}{timestamp}"
        return base64.b64encode(data_to_encode.encode()).decode(), timestamp
   

    def initiate_stk_push(
        self, phone_number, amount, order_id, description="Event Ticket"
    ):
        try:
            access_token = self._get_access_token()
            if not access_token:
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

            response = requests.post(
                f"{self.BASE_URL}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers=headers,
                timeout=30,
            )

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
            return {"success": False, "error": str(e)}