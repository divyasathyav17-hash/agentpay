# AgentPay – GlobalShopping Pay

AI agent that compares product prices across countries, calculates the true
landed cost (price + shipping + FX fee + duty), checks seller trust, detects
fraud, and completes checkout via PayPal Sandbox.

## Features
- Natural language product search
- Landed cost calculator (FX fee, duty, shipping)
- Seller trust score and buy / wait verdict
- Price prediction and price-drop alerts
- Fraud detection (Isolation Forest ML + rules)
- PayPal Sandbox checkout (test money only)
- User login / register
- Real prices via SerpAPI (optional) and a demo mode

## Tech Stack
Python (Flask), scikit-learn, HTML/CSS/JS, PayPal Sandbox API, SerpAPI

## Run locally
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your own keys
3. `python app.py`
4. Open http://127.0.0.1:5000

## Note
Demo mode uses mock/estimated data. Duty and FX rates are estimates.
Payments run on PayPal Sandbox only (no real money).
