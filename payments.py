# ============================================================
# REAL-MONEY MEMBERSHIP PAYMENTS
# Manual verification workflow for bKash/Nagad/Bybit.
# No automatic payment claim is accepted without provider verification.
# ============================================================
import time, uuid, logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import BKASH_NUMBER, NAGAD_NUMBER, BYBIT_UID, ADMIN_ID, ADMIN_USERNAME
from database import db, get_user, activate_premium, activate_vip, add_activity, record_transaction

logger=logging.getLogger(__name__)
payments=db["membership_payments"]

def _now(): return int(time.time())
def _id(): return "PAY-"+uuid.uuid4().hex[:12].upper()

def create_payment(user_id, product, price, method):
    doc={"payment_id":_id(),"user_id":int(user_id),"product":product,"price":float(price),"method":method,"status":"pending","created_at":_now()}
    payments.insert_one(doc); return doc

def get_payment(pid): return payments.find_one({"payment_id":str(pid)})
def pending(limit=50): return list(payments.find({"status":"pending"},{"_id":0}).sort("created_at",1).limit(limit))

def submit_reference(pid, reference):
    reference=str(reference).strip()[:200]
    if not reference: return False
    r=payments.update_one({"payment_id":pid,"status":"pending"},{"$set":{"reference":reference,"submitted_at":_now()}})
    return r.modified_count>0

def approve_payment(pid, admin_id):
    p=get_payment(pid)
    if not p or p.get("status")!="pending" or not p.get("reference"): return False,"Payment is not ready for approval."
    # Atomic status lock prevents double activation.
    locked=payments.update_one({"payment_id":pid,"status":"pending"},{"$set":{"status":"approved","approved_at":_now(),"approved_by":int(admin_id)}})
    if locked.modified_count!=1: return False,"Already processed."
    try:
        if p["product"]=="premium": ok=activate_premium(p["user_id"],30)
        else: ok=activate_vip(p["user_id"],int(p["product"].split(":",1)[1]),30)
        if not ok: raise RuntimeError("membership activation failed")
        add_activity(p["user_id"],f"{p['product']} cash payment approved",0)
        record_transaction(p["user_id"],"membership_cash_payment",int(round(p["price"])),"manual_payment","completed",{"payment_id":pid,"method":p["method"],"reference":p["reference"],"product":p["product"]})
        return True,"Approved."
    except Exception as e:
        logger.exception("membership activation failed")
        payments.update_one({"payment_id":pid},{"$set":{"status":"pending","activation_error":str(e)}})
        return False,"Activation failed; payment returned to pending."

def reject_payment(pid, reason="Rejected"):
    r=payments.update_one({"payment_id":pid,"status":"pending"},{"$set":{"status":"rejected","rejection_reason":str(reason)[:500],"rejected_at":_now()}})
    return r.modified_count>0

def method_keyboard(product):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 bKash",callback_data=f"pay_method_bkash:{product}")],
        [InlineKeyboardButton("📱 Nagad",callback_data=f"pay_method_nagad:{product}")],
        [InlineKeyboardButton("💱 Bybit",callback_data=f"pay_method_bybit:{product}")],
        [InlineKeyboardButton("🏠 Home",callback_data="home")],
    ])

def payment_instructions(method, product, price):
    if method=="bkash": destination=BKASH_NUMBER; label="bKash Send Money"
    elif method=="nagad": destination=NAGAD_NUMBER; label="Nagad Send Money"
    else: destination=BYBIT_UID; label="Bybit UID"
    return (f"💳 **PAYMENT — {product.upper()}**\n\n💰 Amount: **৳{price:g}**\n📌 Method: **{label}**\n📥 Account/UID: `{destination}`\n\n"
            "After payment, send your **Transaction ID / payment reference** using the button below.\n"
            "⚠️ Membership activates only after Admin verifies the payment.")

async def payment_text_handler(update, context):
    """Accept a user-submitted transaction/reference after payment."""
    user=update.effective_user; msg=update.effective_message
    if not user or not msg: return False
    pid=context.user_data.get("payment_reference_id")
    if not pid: return False
    p=get_payment(pid)
    if not p or int(p.get("user_id",0))!=user.id or p.get("status")!="pending":
        context.user_data.pop("payment_reference_id",None); return False
    ref=(msg.text or "").strip()
    if not submit_reference(pid,ref):
        await msg.reply_text("❌ Could not submit the transaction reference. Please try again.")
        return True
    context.user_data.pop("payment_reference_id",None)
    try:
        await context.bot.send_message(int(ADMIN_ID), f"💳 New membership payment\nID: {pid}\nUser: {user.id}\nProduct: {p.get('product')}\nAmount: ৳{float(p.get('price',0)):g}\nMethod: {p.get('method')}\nReference: {ref}")
    except Exception: pass
    await msg.reply_text("✅ Payment reference received. Your membership will activate after Admin verification.")
    return True
