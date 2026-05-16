"""
Bot sozlamalari — Render Environment Variables
Bir nechta sayt bilan ishlash
"""
import os
import json

# ========== ASOSIY SOZLAMALAR ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
PAYMENT_GROUP_ID = int(os.environ.get("PAYMENT_GROUP_ID", "0"))
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "uz")

# ========== SAYTLAR (JSON formatida) ==========
# Renderda ENV: SITES = [{"name":"Sayt 1","url":"https://site1.com/api","key":"key1"}]
SITES_JSON = os.environ.get("SITES", "[]")
try:
    SITES = json.loads(SITES_JSON)
except:
    SITES = []

# ... (qolgan joyi avvalgidek) ...

def get_site_by_index(index):
    """Sayt indeksi bo'yicha ma'lumot olish"""
    if 0 <= index < len(SITES):
        return SITES[index]
    return None
