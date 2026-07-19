import discord
from discord.ext import commands, tasks
import json
import random
import time
import os
from flask import Flask
from threading import Thread
from datetime import datetime

# ====================================================================
# --- PHẦN 1: WEB SERVER GIỮ BOT ONLINE (RENDER) ---
# ====================================================================
app = Flask('')
@app.route('/')
def home(): return "✅ Bot Aternos V9 (Full RPG, Queue, Smart Backup) đang chạy!"
def run_web():
    try: app.run(host='0.0.0.0', port=8080)
    except: pass
def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ====================================================================
# --- PHẦN 2: CẤU HÌNH, DATABASE & HÀNG ĐỢI RÚT TIỀN ---
# ====================================================================
TOKEN = os.environ.get('DISCORD_TOKEN')
CONSOLE_CHANNEL_ID = int(os.environ.get('CONSOLE_CHANNEL_ID', 0))
BACKUP_CHANNEL_ID = int(os.environ.get('BACKUP_CHANNEL_ID', 0))

DB_FILE = 'users.json'
data_changed = False
USER_PARTY = {}

def load_db():
    if not os.path.exists(DB_FILE): return {"users": {}, "pending": []}
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "users" not in data: data = {"users": data, "pending": []}
            return data
    except: return {"users": {}, "pending": []}

def save_db(data):
    global data_changed
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
        data_changed = True
    except Exception as e: print(f"Lỗi lưu file: {e}")

async def process_pending_withdrawals(bot_instance):
    db = load_db()
    if not db.get("pending"): return
    
    try:
        console = bot_instance.get_channel(CONSOLE_CHANNEL_ID) or await bot_instance.fetch_channel(CONSOLE_CHANNEL_ID)
        if not console: return
        
        print("🔄 Đang xử lý các lệnh rút tiền chờ...")
        for item in db["pending"][:]:
            await console.send(f'eco give {item["mc_name"]} {item["amount"]}')
            db["pending"].remove(item)
            
        save_db(db)
        print("✅ Đã gửi hết lệnh chờ.")
    except Exception as e:
        print(f"❌ Lỗi gửi hàng đợi: {e}")

# ====================================================================
# --- PHẦN 3: CƠ CHẾ RPG (BOSS, VŨ KHÍ, LEVEL) ---
# ====================================================================
BOSSES = [
    {"name": "Ma Vương Râu Trắng 👹", "drop": "Sừng Ma Vương", "drop_price": 200},
    {"name": "Rồng Thần Hủy Diệt 🐉", "drop": "Vảy Rồng Thần", "drop_price": 400},
    {"name": "Titan Hắc Ám 🧟‍♂️", "drop": "Lõi Titan", "drop_price": 300},
    {"name": "Quái Vật Hồ Ness 🦕", "drop": "Mắt Quái Biển", "drop_price": 150}
]

WEAPONS = {
    "Kiếm Gỗ": {"price": 50, "power": 15, "emoji": "🪵", "desc": "Tăng 15 sức mạnh"},
    "Kiếm Sắt": {"price": 150, "power": 30, "emoji": "🗡️", "desc": "Tăng 30 sức mạnh"},
    "Kiếm Kim Cương": {"price": 500, "power": 55, "emoji": "💎", "desc": "Tăng 55 sức mạnh"},
    "Thánh Kiếm Excalibur": {"price": 1500, "power": 120, "emoji": "⚔️", "desc": "Vũ khí huyền thoại (+120 SM)"}
}

def add_xp(db, uid, amount):
    if uid not in db["users"]: return ""
    db["users"][uid]["xp"] = db["users"][uid].get("xp", 0) + amount
    level = db["users"][uid].get("level", 1)
    xp_needed = level * 100
    if db["users"][uid]["xp"] >= xp_needed:
        db["users"][uid]["level"] = level + 1
        db["users"][uid]["xp"] -= xp_needed
        db["users"][uid]["base_power"] = db["users"][uid].get("base_power", 0) + 5
        return f"\n🌟 **THĂNG CẤP!** Bạn đã đạt Level {db['users'][uid]['level']}! Tăng +5 Sức mạnh cơ bản."
    return ""

def get_total_power(db, uid):
    u = db["users"].get(uid, {})
    base = u.get("base_power", 0) + (u.get("level", 1) * 2)
    w_power = u.get("power", 0)
    return base + w_power

# ====================================================================
# --- PHẦN 4: GIAO DIỆN (UI VIEWS & MODALS) ---
# ====================================================================
class MoviVaoDoiView(discord.ui.View):
    def __init__(self, leader: discord.Member, target: discord.Member):
        super().__init__(timeout=60)
        self.leader, self.target = leader, target

    @discord.ui.button(label="Đồng ý vào đội", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target.id: return await interaction.response.send_message("❌ Lời mời không dành cho bạn!", ephemeral=True)
        lid, tid = str(self.leader.id), str(self.target.id)
        if lid not in USER_PARTY: USER_PARTY[lid] = lid
        if len([u for u, p in USER_PARTY.items() if p == lid]) >= 4:
            self.stop(); return await interaction.response.send_message("❌ Đội này đã đầy (Tối đa 4)!", ephemeral=True)
        USER_PARTY[tid] = lid
        await interaction.response.edit_message(content=f"🤝 **{self.target.display_name}** đã gia nhập tổ đội của **{self.leader.display_name}**!", view=None)
        self.stop()

class ShopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    async def buy_weapon(self, interaction, weapon_name):
        db, uid = load_db(), str(interaction.user.id)
        if uid not in db["users"]: return await interaction.response.send_message("❌ Chưa `/link`!", ephemeral=True)
        price, power = WEAPONS[weapon_name]["price"], WEAPONS[weapon_name]["power"]
        if db["users"][uid].get("balance", 0) < price: return await interaction.response.send_message(f"❌ Không đủ **${price}**!", ephemeral=True)
        if db["users"][uid].get("power", 0) >= power: return await interaction.response.send_message("❌ Bạn đang có vũ khí mạnh ngang hoặc hơn rồi!", ephemeral=True)
        
        db["users"][uid]["balance"] -= price
        db["users"][uid]["weapon"], db["users"][uid]["power"] = weapon_name, power
        save_db(db)
        await interaction.response.send_message(f"✅ Đã trang bị **{weapon_name}** {WEAPONS[weapon_name]['emoji']}!", ephemeral=True)

    @discord.ui.button(label="Kiếm Gỗ ($50)", style=discord.ButtonStyle.secondary, emoji="🪵")
    async def btn_wood(self, i, b): await self.buy_weapon(i, "Kiếm Gỗ")
    @discord.ui.button(label="Kiếm Sắt ($150)", style=discord.ButtonStyle.secondary, emoji="🗡️")
    async def btn_iron(self, i, b): await self.buy_weapon(i, "Kiếm Sắt")
    @discord.ui.button(label="Kiếm Kim Cương ($500)", style=discord.ButtonStyle.primary, emoji="💎")
    async def btn_diamond(self, i, b): await self.buy_weapon(i, "Kiếm Kim Cương")
    @discord.ui.button(label="Thánh Kiếm ($1500)", style=discord.ButtonStyle.danger, emoji="⚔️", row=1)
    async def btn_excal(self, i, b): await self.buy_weapon(i, "Thánh Kiếm Excalibur")

class ThachDauView(discord.ui.View):
    def __init__(self, initiator, opponent, amount):
        super().__init__(timeout=60)
        self.initiator, self.opponent, self.amount = initiator, opponent, amount

    @discord.ui.button(label="Đồng ý chiến!", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id: return await interaction.response.send_message("❌ Không phải cho bạn!", ephemeral=True)
        db, id1, id2 = load_db(), str(self.initiator.id), str(self.opponent.id)
        if db["users"].get(id1, {}).get("balance", 0) < self.amount or db["users"].get(id2, {}).get("balance", 0) < self.amount:
            self.stop(); return await interaction.response.send_message("❌ Ai đó không đủ tiền cược!", ephemeral=True)

        db["users"][id1]["balance"] -= self.amount
        db["users"][id2]["balance"] -= self.amount
        
        weight1, weight2 = 50 + get_total_power(db, id1), 50 + get_total_power(db, id2)
        winner = random.choices([self.initiator, self.opponent], weights=[weight1, weight2])[0]
        prize = self.amount * 2
        db["users"][str(winner.id)]["balance"] += prize
        save_db(db)
        
        msg = f"⚔️ **KẾT QUẢ TRẬN ĐẤU** ⚔️\n**{self.initiator.display_name}** 🆚 **{self.opponent.display_name}**\n\n🏆 Kẻ chiến thắng là: **{winner.mention}**! Nhận **${prize}**."
        await interaction.response.edit_message(content=msg, view=None)
        self.stop()

    @discord.ui.button(label="Từ chối", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id: return
        await interaction.response.edit_message(content="🛡️ Lời mời thách đấu đã bị từ chối.", view=None)
        self.stop()

# --- BẦU CUA ---
class BetModal(discord.ui.Modal):
    def __init__(self, animal, emoji, baucua_view):
        super().__init__(title=f"Cược cho {animal.capitalize()} {emoji}")
        self.animal, self.emoji, self.baucua_view = animal, emoji, baucua_view
        self.bet_amount = discord.ui.TextInput(label="Nhập tiền cược:", placeholder="VD: 50", required=True)
        self.add_item(self.bet_amount)

    async def on_submit(self, interaction: discord.Interaction):
        try: amount = int(self.bet_amount.value)
        except: return await interaction.response.send_message("❌ Chỉ nhập số!", ephemeral=True)
        if amount <= 0: return await interaction.response.send_message("❌ Tiền phải > 0!", ephemeral=True)

        db, uid = load_db(), str(interaction.user.id)
        if uid not in db["users"]: return await interaction.response.send_message("❌ Chưa `/link`!", ephemeral=True)
        if db["users"][uid].get("balance", 0) < amount: return await interaction.response.send_message(f"❌ Không đủ ${amount}!", ephemeral=True)
            
        db["users"][uid]["balance"] -= amount
        save_db(db)
        if uid not in self.baucua_view.bets: self.baucua_view.bets[uid] = []
        self.baucua_view.bets[uid].append({"animal": self.animal, "amount": amount})
        await interaction.response.send_message(f"✅ Đã cược **${amount}** vào **{self.animal.capitalize()}** {self.emoji}", ephemeral=True)

class BauCuaView(discord.ui.View):
    def __init__(self, host_id):
        super().__init__(timeout=180)
        self.host_id, self.bets = host_id, {}
    async def prompt_bet(self, i, choice, emoji): await i.response.send_modal(BetModal(choice, emoji, self))
    @discord.ui.button(label="Bầu", emoji="🥒")
    async def btn_b(self, i, b): await self.prompt_bet(i, "bầu", "🥒")
    @discord.ui.button(label="Cua", emoji="🦀")
    async def btn_c(self, i, b): await self.prompt_bet(i, "cua", "🦀")
    @discord.ui.button(label="Tôm", emoji="🦐")
    async def btn_t(self, i, b): await self.prompt_bet(i, "tôm", "🦐")
    @discord.ui.button(label="Cá", emoji="🐟", row=1)
    async def btn_ca(self, i, b): await self.prompt_bet(i, "cá", "🐟")
    @discord.ui.button(label="Gà", emoji="🐔", row=1)
    async def btn_g(self, i, b): await self.prompt_bet(i, "gà", "🐔")
    @discord.ui.button(label="Nai", emoji="🦌", row=1)
    async def btn_n(self, i, b): await self.prompt_bet(i, "nai", "🦌")

    @discord.ui.button(label="🎲 CHỐT SỔ & LẮC", style=discord.ButtonStyle.danger, row=2)
    async def btn_roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id: return await interaction.response.send_message("❌ Chỉ chủ bàn!", ephemeral=True)
        self.stop()
        ket_qua = [random.choice(['bầu', 'cua', 'tôm', 'cá', 'gà', 'nai']) for _ in range(3)]
        db, msg = load_db(), f"🎲 **KẾT QUẢ:** [ **{' - '.join([x.capitalize() for x in ket_qua])}** ]\n\n**BẢNG TRẢ THƯỞNG:**\n"
        if not self.bets: msg += "Không ai cược cả!"
        else:
            for uid, bets in self.bets.items():
                tong_nhan, tong_cuoc = 0, sum(b['amount'] for b in bets)
                for b in bets:
                    if (so_lan := ket_qua.count(b['animal'])) > 0: tong_nhan += b['amount'] + (b['amount'] * so_lan)
                if tong_nhan > 0: db["users"][uid]["balance"] += tong_nhan; msg += f"<@{uid}>: Đặt **${tong_cuoc}** ➡️ Thắng **${tong_nhan}** 🎉\n"
                else: msg += f"<@{uid}>: Thua sạch **${tong_cuoc}** 😢\n"
        save_db(db)
        await interaction.response.edit_message(embed=discord.Embed(title="🎲 BÀN ĐÃ ĐÓNG", description=msg, color=discord.Color.gold()), view=None)

# ====================================================================
# --- PHẦN 5: BOT STARTUP & BACKUP LOOP ---
# ====================================================================
class MyBot(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=discord.Intents.default())
    async def setup_hook(self): await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f'✅ Bot {bot.user.name} V9 ĐÃ SẴN SÀNG!')
    if BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=10):
                if msg.author == bot.user and msg.attachments and msg.attachments[0].filename == 'users.json':
                    await msg.attachments[0].save(DB_FILE)
                    print("☁️ Đã khôi phục dữ liệu!")
                    break
        except Exception as e: print("Không tìm thấy backup cũ:", e)
        
    await process_pending_withdrawals(bot)
    
    if not auto_backup_task.is_running(): auto_backup_task.start()
    await bot.change_presence(activity=discord.Game(name="/ruongdo | /pay | /sanboss"))

@tasks.loop(minutes=3)
async def auto_backup_task():
    global data_changed
    if data_changed and BACKUP_CHANNEL_ID:
        try:
            channel = await bot.fetch_channel(BACKUP_CHANNEL_ID)
            async for msg in channel.history(limit=20):
                if msg.author == bot.user: await msg.delete()
            await channel.send(f"☁️ **SMART BACKUP V9** ({datetime.now().strftime('%H:%M')}):", file=discord.File(DB_FILE))
            data_changed = False
        except: pass

# ====================================================================
# --- PHẦN 6: LỆNH SLASH COMMANDS ---
# ====================================================================
@bot.tree.command(name="link", description="Tạo hồ sơ nhân vật (Liên kết tài khoản game).")
async def link(interaction: discord.Interaction, mc_name: str):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: 
        db["users"][uid] = {"balance": 0, "mc_name": mc_name, "weapon": "Tay không", "power": 0, "level": 1, "xp": 0, "base_power": 0, "inventory": {}, "last_daily": ""}
        save_db(db); await interaction.response.send_message(f"✅ Đã tạo hồ sơ: **{mc_name}**.")
    else: await interaction.response.send_message("❌ Bạn đã có hồ sơ rồi!", ephemeral=True)

@bot.tree.command(name="vi", description="Xem thẻ nhân vật RPG.")
async def vi(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Hãy `/link`!", ephemeral=True)
    u = db["users"][uid]
    total_pw = get_total_power(db, uid)
    
    embed = discord.Embed(title=f"📜 THẺ NHÂN VẬT: {interaction.user.display_name}", color=discord.Color.gold())
    embed.add_field(name="🔹 Cấp độ", value=f"**Lv {u.get('level', 1)}** (XP: {u.get('xp', 0)}/{u.get('level', 1)*100})", inline=True)
    embed.add_field(name="💳 Tài sản", value=f"**${u.get('balance', 0)}**", inline=True)
    embed.add_field(name="⚔️ Sức mạnh Tổng", value=f"**{total_pw}**", inline=True)
    embed.add_field(name="🛡️ Vũ khí trang bị", value=f"{u.get('weapon', 'Tay không')} (+{u.get('power', 0)} SM)", inline=False)
    inv_count = sum(u.get('inventory', {}).values())
    embed.add_field(name="🎒 Rương đồ", value=f"Đang có {inv_count} vật phẩm. Dùng `/ruongdo` để xem.", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shop", description="Mở cửa hàng vũ khí.")
async def shop(interaction: discord.Interaction):
    embed = discord.Embed(title="🛒 CỬA HÀNG VŨ KHÍ", color=discord.Color.purple())
    for name, data in WEAPONS.items(): embed.add_field(name=f"{data['emoji']} {name} - ${data['price']}", value=f"*{data['desc']}*", inline=False)
    await interaction.response.send_message(embed=embed, view=ShopView())

@bot.tree.command(name="ruongdo", description="Xem các vật phẩm hiếm trong Rương.")
async def ruongdo(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: return await interaction.response.send_message("❌ Lỗi!", ephemeral=True)
    inventory = db["users"][uid].get("inventory", {})
    if not inventory: return await interaction.response.send_message("🎒 Rương đồ của bạn đang trống rỗng!")
    
    msg = "🎒 **RƯƠNG ĐỒ CỦA BẠN:**\n"
    for item, qty in inventory.items():
        if qty > 0: msg += f"- **{item}**: {qty} cái\n"
    await interaction.response.send_message(msg)

@bot.tree.command(name="banvatpham", description="Bán vật phẩm hiếm lấy tiền.")
async def banvatpham(interaction: discord.Interaction, ten_vat_pham: str, so_luong: int):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"] or so_luong <= 0: return await interaction.response.send_message("❌ Lỗi!", ephemeral=True)
    inventory = db["users"][uid].get("inventory", {})
    
    if inventory.get(ten_vat_pham, 0) < so_luong: return await interaction.response.send_message(f"❌ Không đủ **{ten_vat_pham}**!", ephemeral=True)
    item_price = 50
    for b in BOSSES:
        if b["drop"] == ten_vat_pham: item_price = b["drop_price"]

    earned = item_price * so_luong
    db["users"][uid]["inventory"][ten_vat_pham] -= so_luong
    if db["users"][uid]["inventory"][ten_vat_pham] == 0: del db["users"][uid]["inventory"][ten_vat_pham]
    db["users"][uid]["balance"] += earned
    save_db(db)
    await interaction.response.send_message(f"💸 Đã bán **{so_luong}x {ten_vat_pham}** lấy **${earned}**!")

@bot.tree.command(name="lapdoi", description="Mời người chơi khác vào tổ đội.")
async def lapdoi(interaction: discord.Interaction, nguoi_choi: discord.Member):
    lid, tid = str(interaction.user.id), str(nguoi_choi.id)
    if lid == tid: return await interaction.response.send_message("❌ Lỗi!", ephemeral=True)
    view = MoviVaoDoiView(interaction.user, nguoi_choi)
    await interaction.response.send_message(f"🚩 **{interaction.user.display_name}** đang mời **{nguoi_choi.mention}** vào Tổ Đội!", view=view)

@bot.tree.command(name="thongtindoi", description="Xem thông tin Tổ Đội.")
async def thongtindoi(interaction: discord.Interaction):
    uid, db = str(interaction.user.id), load_db()
    if uid not in USER_PARTY: return await interaction.response.send_message("❌ Bạn chưa vào đội!", ephemeral=True)
    party_id = USER_PARTY[uid]
    members = [u for u, p in USER_PARTY.items() if p == party_id]
    
    msg, total_pw = f"🛡️ **THÔNG TIN TỔ ĐỘI**\n\n", 0
    for m in members:
        pw = get_total_power(db, m)
        total_pw += pw
        msg += f"👤 <@{m}> (Lv {db['users'].get(m,{}).get('level',1)}) - Lực chiến: {pw}\n"
    msg += f"\n🔥 **TỔNG LỰC CHIẾN ĐỘI:** {total_pw}"
    await interaction.response.send_message(msg)

@bot.tree.command(name="sanboss", description="Cùng Tổ đội đánh Boss (Phí: $50/đội).")
async def sanboss(interaction: discord.Interaction):
    uid, db = str(interaction.user.id), load_db()
    if uid not in USER_PARTY or USER_PARTY[uid] != uid: return await interaction.response.send_message("❌ Chỉ Đội trưởng được dùng!", ephemeral=True)
    if db["users"].get(uid, {}).get("balance", 0) < 50: return await interaction.response.send_message("❌ Cần $50!", ephemeral=True)
        
    members = [u for u, p in USER_PARTY.items() if p == uid]
    total_power = sum(get_total_power(db, m) for m in members)
    db["users"][uid]["balance"] -= 50
    
    boss = random.choice(BOSSES)
    win_chance = min(95, 10 + int(total_power * 0.5))
    
    if random.randint(1, 100) <= win_chance:
        cash, xp = random.randint(100, 200), random.randint(30, 80)
        msg = f"🎉 **CHIẾN THẮNG!** Đội bạn đã diệt **{boss['name']}**!\n💰 Mỗi người nhận: **${cash}** & **{xp} XP**\n"
        for m in members:
            db["users"][m]["balance"] += cash
            msg += add_xp(db, m, xp)
            if random.random() < 0.40:
                if "inventory" not in db["users"][m]: db["users"][m]["inventory"] = {}
                db["users"][m]["inventory"][boss["drop"]] = db["users"][m]["inventory"].get(boss["drop"], 0) + 1
                msg += f"\n🎁 <@{m}> nhặt được 1x **{boss['drop']}**!"
    else: msg = f"💀 **THẤT BẠI!** **{boss['name']}** quá mạnh. Mất $50 phí."
    save_db(db); await interaction.response.send_message(msg)

@bot.tree.command(name="santhu", description="Săn quái cá nhân kiếm XP & Tiền (Phí $10).")
async def santhu(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"] or db["users"][uid].get("balance", 0) < 10: return await interaction.response.send_message("❌ Cần $10!", ephemeral=True)
    db["users"][uid]["balance"] -= 10
    
    pw = get_total_power(db, uid)
    if random.randint(1, 100) <= min(90, 30 + pw):
        r_cash, r_xp = random.randint(20, 50), random.randint(15, 30)
        db["users"][uid]["balance"] += r_cash
        msg = f"🎉 Bạn hạ quái thú! Nhận **${r_cash}** & **{r_xp} XP**.{add_xp(db, uid, r_xp)}"
    else: msg = f"💀 Quái vật đánh bại bạn. Mất trắng $10!"
    save_db(db); await interaction.response.send_message(msg)

@bot.tree.command(name="thachdau", description="Thách đấu người chơi khác.")
async def thachdau(interaction: discord.Interaction, nguoi_choi: discord.Member, so_tien: int):
    if so_tien <= 0 or nguoi_choi == interaction.user: return await interaction.response.send_message("❌ Lỗi!", ephemeral=True)
    await interaction.response.send_message(f"⚔️ **{interaction.user.display_name}** đang thách đấu **{nguoi_choi.mention}** ($**{so_tien}**)", view=ThachDauView(interaction.user, nguoi_choi, so_tien))

@bot.tree.command(name="baucua", description="Tạo bàn Bầu Cua Tôm Cá.")
async def baucua(interaction: discord.Interaction):
    embed = discord.Embed(title="🎪 BÀN BẦU CUA", description=f"Chủ bàn: **{interaction.user.display_name}**", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=BauCuaView(host_id=interaction.user.id))

@bot.tree.command(name="daily", description="Điểm danh nhận quà mỗi ngày (Sau 0h đêm).")
async def daily(interaction: discord.Interaction):
    db, uid = load_db(), str(interaction.user.id)
    if uid not in db["users"]: 
        return await interaction.response.send_message("❌ Bạn chưa `/link` tài khoản!", ephemeral=True)
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    last_date = db["users"][uid].get("last_daily", "")
    
    if last_date == current_date: 
        return await interaction.response.send_message("⏳ Bạn đã nhận quà ngày hôm nay rồi! Vui lòng quay lại sau 00:00 nhé.", ephemeral=True)
    
    reward = random.randint(20, 50)
    db["users"][uid]["last_daily"] = current_date
    db["users"][uid]["balance"] = db["users"][uid].get("balance", 0) + reward
    
    save_db(db)
    await interaction.response.send_message(f"🎁 Điểm danh thành công! Bạn nhận được **${reward}**. Hẹn gặp lại vào ngày mai!")

@bot.tree.command(name="pay", description="Chuyển tiền cho người chơi khác.")
async def pay(interaction: discord.Interaction, nguoi_nhan: discord.Member, so_tien: int):
    db = load_db()
    uid, tid = str(interaction.user.id), str(nguoi_nhan.id)
    
    if uid not in db["users"] or tid not in db["users"]:
        return await interaction.response.send_message("❌ Một trong hai người chưa tạo hồ sơ (`/link`)!", ephemeral=True)
    if so_tien <= 0 or db["users"][uid]["balance"] < so_tien:
        return await interaction.response.send_message("❌ Số dư không đủ hoặc số tiền không hợp lệ!", ephemeral=True)
    
    db["users"][uid]["balance"] -= so_tien
    db["users"][tid]["balance"] += so_tien
    save_db(db)
    
    await interaction.response.send_message(f"💸 **{interaction.user.display_name}** đã chuyển thành công **${so_tien}** cho **{nguoi_nhan.display_name}**!")

@bot.tree.command(name="ruttien", description="Rút tiền vào Game (Tự động chuyển khi Server mở).")
async def ruttien(interaction: discord.Interaction, so_tien: int):
    db = load_db()
    uid = str(interaction.user.id)
    
    if uid not in db["users"] or so_tien <= 0 or db["users"][uid]["balance"] < so_tien:
        return await interaction.response.send_message("❌ Không đủ tiền hoặc chưa tạo hồ sơ!", ephemeral=True)
    
    mc_name = db["users"][uid]["mc_name"]
    db["users"][uid]["balance"] -= so_tien
    
    db["pending"].append({"uid": uid, "amount": so_tien, "mc_name": mc_name})
    save_db(db)
    
    await interaction.response.send_message(f"✅ Đã trừ **${so_tien}** trong ví Discord.\n⏳ Yêu cầu rút tiền vào nhân vật **{mc_name}** đã được đưa vào hàng đợi. Tiền sẽ tự động vào túi bạn khi Server Minecraft đang chạy!")
    
    await process_pending_withdrawals(bot)

# ====================================================================
# --- KHỞI ĐỘNG ---
# ====================================================================
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
