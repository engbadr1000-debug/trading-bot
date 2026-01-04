import imaplib
import email
import time
import os
from binance.client import Client
from flask import Flask
from threading import Thread

# --- نظام سحب المفاتيح السرية من إعدادات Render ---
BINANCE_API_KEY = os.getenv('BINANCE_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_SECRET')
GMAIL_USER = os.getenv('GMAIL_EMAIL')
GMAIL_PASS = os.getenv('GMAIL_APP_PASSWORD')

# الربط مع بينانس (سيعمل من سيرفر ألمانيا بنجاح)
client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

# --- سيرفر داخلي لمنع "نوم" السيرفر (Keep-Alive) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Active and Guarding the Market!"

def run_web_server():
    # Render يطلب العمل على بورت 10000 أو المتغير المتاح
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- المحرك الحسابي لتوازن الفرص ---
def get_total_equity():
    """حساب إجمالي قيمة المحفظة (كاش + عملات) لضمان توازن الـ 20% لكل صفقة"""
    try:
        account_info = client.get_account()
        total_val = 0
        for asset in account_info['balances']:
            free = float(asset['free'])
            locked = float(asset['locked'])
            total_asset = free + locked
            if total_asset > 0:
                if asset['asset'] == 'USDT':
                    total_val += total_asset
                else:
                    try:
                        price = float(client.get_symbol_ticker(symbol=asset['asset'] + 'USDT')['price'])
                        total_val += total_asset * price
                    except:
                        pass # تجاهل الأصول الصغيرة جداً
        return total_val
    except Exception as e:
        print(f"خطأ في حساب السيولة: {e}")
        return 0

# --- تنفيذ الأوامر العسكرية ---
def execute_trade(action, symbol):
    try:
        if action == "BUY":
            print(f"[{time.ctime()}] 🎯 رصد إشارة شراء لـ {symbol}. بدء تأخير الـ 30 ثانية...")
            time.sleep(30) # التأخير الاستراتيجي لضمان توفر السيولة
            
            total_equity = get_total_equity()
            amount_to_spend = total_equity * 0.20 # توازن الفرص 20% من الإجمالي
            
            # فحص السيولة المتاحة فعلياً لتجنب رفض الطلب
            free_usdt = float(client.get_asset_balance(asset='USDT')['free'])
            final_buy_amount = min(amount_to_spend, free_usdt)
            
            if final_buy_amount > 11: # الحد الأدنى للشراء في بينانس هو 10$ تقريباً
                order = client.order_market_buy(symbol=symbol, quoteOrderQty=round(final_buy_amount, 2))
                print(f"✅ تم الشراء بنجاح بمبلغ: {round(final_buy_amount, 2)} USDT")
            else:
                print("❌ السيولة المتاحة غير كافية لتنفيذ صفقة الـ 20%")

        elif action == "SELL":
            print(f"[{time.ctime()}] 🚨 إشارة بيع فورية لـ {symbol}. إخلاء الموقع 100%...")
            asset = symbol.replace('USDT', '')
            asset_balance = client.get_asset_balance(asset=asset)['free']
            
            if float(asset_balance) > 0:
                # البيع بكامل الكمية (Market Order)
                order = client.order_market_sell(symbol=symbol, quantity=asset_balance)
                print(f"✅ تم الخروج وبيع كامل الكمية من {asset}")
            else:
                print(f"⚠ لا يوجد رصيد لبيعه من {asset}")

    except Exception as e:
        print(f"❌ خطأ أثناء التنفيذ: {e}")

# --- نظام مراقبة الإيميل (IMAP) ---
def start_email_monitoring():
    print("🚀 الرادار انطلق من ألمانيا.. في انتظار إشارات TradingView عبر الإيميل...")
    while True:
        try:
            # الاتصال بصندوق البريد
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(GMAIL_USER, GMAIL_PASS)
            mail.select("inbox")
            
            # البحث عن الرسائل غير المقروءة فقط
            _, messages = mail.search(None, '(UNSEEN)')
            
            for num in messages[0].split():
                _, data = mail.fetch(num, '(RFC822)')
                for response_part in data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = msg['subject'].upper()
                        
                        # التوقع: العنوان يكون مثلاً DOGEUSDT BUY
                        if "BUY" in subject:
                            symbol = subject.split()[0]
                            execute_trade("BUY", symbol)
                        elif "SELL" in subject:
                            symbol = subject.split()[0]
                            execute_trade("SELL", symbol)
                
                # وضع علامة "مقروء" على الرسالة لعدم تكرارها
                mail.store(num, '+FLAGS', '\\Seen')
            
            mail.logout()
            time.sleep(10) # فحص الإيميل كل 10 ثوانٍ
        except Exception as e:
            print(f"🔄 إعادة الاتصال بالرادار... {e}")
            time.sleep(20)

# --- تشغيل المنظومة ---
if __name__ == "__main__":
    # 1. تشغيل سيرفر الويب في خلفية (Thread)
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    # 2. تشغيل رادار الإيميل في المسار الرئيسي
    start_email_monitoring()
