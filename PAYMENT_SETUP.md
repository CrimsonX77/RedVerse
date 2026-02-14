# 💳 Stripe Payment Setup Guide

This guide will help you set up the RedVerse payment system to accept real donations through Stripe.

## Current Status

✅ **Backend Server**: Fully implemented and ready to use  
✅ **Frontend Integration**: Already configured in `support.html`  
⚠️ **Stripe Keys**: Need to be configured with your account

---

## Prerequisites

1. **Python 3.10+** with pip
2. **Stripe Account** (free to create at https://stripe.com)
3. **Dependencies installed** (see Installation section)

---

## Quick Start

### 1. Create a Stripe Account

1. Go to https://stripe.com and sign up
2. Complete the account verification process
3. Navigate to https://dashboard.stripe.com/apikeys

### 2. Get Your API Keys

In your Stripe Dashboard:

1. Click on **Developers** → **API keys**
2. You'll see two types of keys:
   - **Publishable key** (`pk_test_...` for test mode)
   - **Secret key** (`sk_test_...` for test mode)

### 3. Configure Your Keys

#### Update Backend (.env file)

Copy `.env.example` to `.env` if you haven't already:

```bash
cp .env.example .env
```

Edit `.env` and add your **Secret Key**:

```env
STRIPE_SECRET_KEY=sk_test_YOUR_SECRET_KEY_HERE
```

⚠️ **IMPORTANT**: Never commit your secret key to version control! The `.env` file is already in `.gitignore`.

#### Update Frontend (support.html)

Open `support.html` and find line 498:

```javascript
const stripe = Stripe('pk_test_51SzrZ71vwsNjD6TFghJeXjtqWjHcUwjcd3Y8vaUAKxMxn2wSrzkwM8V0cYTS3BeyWtJ76e3qyeS8PsBb97Zml4YS00RBoIraVk');
```

Replace the key with your **Publishable Key**:

```javascript
const stripe = Stripe('pk_test_YOUR_PUBLISHABLE_KEY_HERE');
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install just the payment server dependencies:

```bash
pip install flask flask-cors stripe python-dotenv
```

### 5. Start the Server

**Option A: Using the shell script**
```bash
chmod +x server.sh
./server.sh
```

**Option B: Direct Python**
```bash
python3 server.py
```

You should see:
```
✅ Stripe configured with key: sk_test...
🔥 RedVerse Payment Server starting on port 5000
   Health check: http://localhost:5000/health
   Payment endpoint: http://localhost:5000/create-payment-intent
```

### 6. Test the Integration

1. Keep the server running
2. Open `support.html` in a web browser
3. Select a donation amount or enter a custom amount
4. Use a test card number:
   - **Card number**: `4242 4242 4242 4242`
   - **Expiry**: Any future date (e.g., `12/25`)
   - **CVC**: Any 3 digits (e.g., `123`)
   - **ZIP**: Any 5 digits (e.g., `12345`)

5. Click "Feed the Altar"
6. You should see: "🔥 Offering accepted. The Church thanks you. 🔥"

### 7. Verify in Stripe Dashboard

1. Go to https://dashboard.stripe.com/test/payments
2. You should see your test payment listed
3. Click on it to see details

---

## Going Live (Production Mode)

When you're ready to accept real payments:

### 1. Activate Your Stripe Account

Complete Stripe's activation process:
- Business information
- Bank account details for payouts
- Identity verification

### 2. Get Live API Keys

1. In Stripe Dashboard, toggle from **Test mode** to **Live mode** (top right)
2. Go to **Developers** → **API keys**
3. Copy your **Live** keys (they start with `pk_live_...` and `sk_live_...`)

### 3. Update Configuration

**Backend (.env):**
```env
STRIPE_SECRET_KEY=sk_live_YOUR_LIVE_SECRET_KEY
FLASK_ENV=production
```

**Frontend (support.html):**
```javascript
const stripe = Stripe('pk_live_YOUR_LIVE_PUBLISHABLE_KEY');
```

### 4. Deploy Securely

- ✅ Use HTTPS for your website
- ✅ Keep your secret key secure (environment variables, not in code)
- ✅ Set up proper error logging
- ✅ Consider setting up Stripe webhooks for payment confirmations

---

## API Endpoints

### Health Check
```bash
GET /health
```

Returns server status and configuration:
```json
{
  "status": "healthy",
  "service": "RedVerse Payment Server",
  "stripe_configured": true
}
```

### Create Payment Intent
```bash
POST /create-payment-intent
Content-Type: application/json

{
  "amount": 500  // Amount in cents ($5.00)
}
```

Returns:
```json
{
  "clientSecret": "pi_xxx_secret_xxx"
}
```

### Webhook (Optional)
```bash
POST /webhook
```

Receives payment events from Stripe. To use:
1. Set up a webhook in Stripe Dashboard
2. Add your webhook secret to `.env`:
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET
   ```

---

## Troubleshooting

### "Backend not connected" Error

**Problem**: Frontend can't reach the backend server.

**Solution**: 
- Make sure `server.py` is running
- Check that it's running on port 5000
- If using a different port, update the fetch URL in `support.html`

### "Invalid API Key" Error

**Problem**: Stripe secret key is incorrect or not set.

**Solution**:
- Check that `STRIPE_SECRET_KEY` is set in `.env`
- Verify the key is correct (copy from Stripe Dashboard)
- Make sure you're using test keys (`sk_test_...`) in test mode

### Payment Succeeds but No Confirmation

**Problem**: Payment works but you don't get notified.

**Solution**: Set up webhooks (see Webhook section above) to receive payment events.

### CORS Error in Browser

**Problem**: Browser blocks request due to CORS policy.

**Solution**: 
- The server already has CORS enabled via `flask-cors`
- If still having issues, check browser console for specific error
- Make sure the server URL matches what's in `support.html`

---

## Security Best Practices

1. **Never commit secret keys** - Always use `.env` and keep it in `.gitignore`
2. **Use HTTPS in production** - Required by Stripe for live mode
3. **Validate amounts server-side** - Already implemented (min $0.50, max $999,999.99)
4. **Set up webhook secrets** - Verify webhook events are from Stripe
5. **Monitor your Stripe Dashboard** - Watch for suspicious activity
6. **Keep dependencies updated** - Regularly update `pip install --upgrade stripe flask`

---

## Test Card Numbers

Stripe provides test cards for different scenarios:

| Card Number | Scenario |
|-------------|----------|
| `4242 4242 4242 4242` | Successful payment |
| `4000 0000 0000 0002` | Card declined |
| `4000 0000 0000 9995` | Insufficient funds |
| `4000 0000 0000 0127` | Incorrect CVC |
| `4000 0000 0000 0069` | Expired card |

More test cards: https://stripe.com/docs/testing

---

## Additional Resources

- **Stripe Documentation**: https://stripe.com/docs
- **Payment Intents Guide**: https://stripe.com/docs/payments/payment-intents
- **Stripe Dashboard**: https://dashboard.stripe.com
- **Stripe Support**: https://support.stripe.com

---

## Questions?

If you encounter issues:
1. Check the server logs for error messages
2. Verify your API keys are correct
3. Review the Troubleshooting section above
4. Check Stripe's documentation
5. Contact Stripe support for payment-specific issues

---

**The Church is ready to accept offerings. Feed the altar. 🔥**
