# UtopiaMafiaBot — To‘liq Product Specification (v1)

Ushbu hujjat Telegram’dagi Mafia bot uchun yakuniy konsept, permission tizimi, o‘yin oqimi, shop/economy, kazino va boshqaruv panellarini bitta joyga jamlaydi.

## 1) Bot arxitekturasi

Bot 2 asosiy kontekstda ishlaydi:

- **Group chat (o‘yin jarayoni):** lobby, join, start, tun, kun, sud, natija, game over.
- **Private chat (dashboard):** profil, shop, kazino, premium, statistika, panel/sozlamalar.

Muhim:

- `/join` yo‘q — faqat inline tugma.
- Vote/skip faqat inline tugmalar.
- Private dashboard imkon qadar bitta xabarni `edit` qilib yangilanadi.

## 2) Role-based permission modeli

### Oddiy user (player)

Ruxsat:

- O‘yinda qatnashish
- `/money`, `/send`, `/give` (balans/inventar doirasida)

Ta’qiqlanadi:

- Admin panel, owner panel
- `/unmoney`, `/unsend`, `/ungive`, `/stop`
- Barcha owner/admin darajadagi buyruqlar

Noto‘g‘ri urinish javobi:

- `❌ Sizda bu buyruqni ishlatish huquqi yo‘q` (*access denied*)

### Admin

Ruxsat:

- `/unmoney`, `/unsend`, `/ungive`
- `/stop`, `/ginfo`
- Private chat’da **admin panel**

Ta’qiqlanadi:

- Owner panel
- `/admin`, `/unadmin`, `/owner`

### Owner

Ruxsat:

- Barcha komandalar
- `/admin`, `/unadmin`, `/owner`
- Admin panel + owner panel

### Partner

Ruxsat:

- `/stop` (faqat o‘z guruhida)
- `/ginfo` (faqat o‘z guruhida)

Ta’qiqlanadi:

- Admin/owner panellar

## 3) Private chat panel ko‘rinish qoidalari

### Oddiy user ko‘radi

- Profil, shop, kazino, premium, stats

### Admin ko‘radi

- User’dagi barcha bo‘limlar
- `👑 Admin Panel`

### Owner ko‘radi

- Admin’dagi barcha bo‘limlar
- `⚙️ Owner Panel`

## 4) Komandalar (yakuniy)

### User komandalar

- `/money <sum>` — reply qilingan user’ga `$` yuborish
- `/send <sum>` — reply qilingan user’ga olmos yuborish
- `/give <item> <count>` — reply qilingan user’ga item berish

Qoidasi:

- Oddiy user: balans/inventar bilan cheklangan
- Admin/Owner: cheksiz rejim

### O‘yin komandalar

- `/newgame` — yangi lobby
- `/startgame` — creator yoki group admin boshlaydi
- `/stop` — owner/admin; partner faqat o‘z guruhida (va TG admin bo‘lsa)

### Admin/Owner komandalar

- `/ginfo`
- `/unmoney`, `/unsend`, `/ungive`

### Faqat Owner

- `/admin`, `/unadmin`, `/owner`

## 5) O‘yin oqimi (group)

1. `/newgame` → lobby xabari + join tugmasi
2. O‘yinchilar inline orqali qo‘shiladi
3. `/startgame`
4. Tun boshlanishi: night media + tun matni + tiriklar ro‘yxati
5. Tungi actionlar private chat’da yashirin bajariladi
6. Tong: natijalar + muhokama taymeri
7. Muhokama (oddiy chat)
8. Ovoz berish (inline)
9. Sud (emoji/sticker qaror)
10. Sud natijasi + rol ochilishi
11. Keyingi tun (cycle)
12. Game over: g‘olib taraf va mukofot

Economy qoida:

- O‘yin oxiri mukofoti: **+20$**
- Olmos umumiy mukofot sifatida berilmaydi (Konchi istisno)

## 6) `/start` welcome va dashboard

Welcome tugmalari:

- Botni guruhga qo‘shish
- Mening guruhlarim
- Til
- Kanal
- Savollar/Yordam
- Do‘kon

Owner panel orqali o‘zgaradi:

- Start matni
- Kanal/sotib olish kontaktlari

Dashboard maydonlari:

- Ism, daraja, unvon, win rate
- `$` va olmos balans
- Premium holat
- Itemlar soni
- Shop/xarid tugmalari
- Premium/VIP group kirishlari

## 7) Economy: 2 valyuta

- **Dollar ($):** oddiy itemlar, kazino, ko‘p shop operatsiyalar
- **Olmos:** premium itemlar, VIP/premium access, qimmat aktivlar

Prinsip:

- Kuchli/rare narsalar ko‘proq olmosga
- Oddiy narsalar dollarga

## 8) Shop bo‘limlari

- Premium itemlar
- Dollar itemlar
- Diamond itemlar
- Protection itemlar
- Mystery box
- Title/Frame
- Premium group access
- VIP group access

## 9) Itemlar (bazaviy ro‘yxat)

- Himoya
- Hujjat
- Osishdan himoya
- Doridan himoya
- Maska
- Qotildan himoya
- Sirpanishdan himoya
- Geroydan himoya
- Miltiq
- Premium chest
- Mystery/Boss box

Item ishlash qoidasi:

- Har item inventar soniga ega
- ON/OFF holat bo‘ladi
- `count=0` bo‘lsa aktiv qilib bo‘lmaydi
- Ko‘p itemlar 1 martalik va ishlaganda kamayadi

## 10) Xarid kontaktlari va linklar

Owner panel’dan yangilanadi:

- Sotuvchi username / user id / tg link
- Rasmiy kanal
- Yangiliklar kanali
- Support link
- Premium/VIP group linklar

## 11) Premium tizimi

Premium *pay-to-win* bo‘lmasligi kerak.

Taklif etiladigan foydalar:

- 2x reward
- Daily premium chest
- Weekly diamonds
- Premium badge/frame
- Elite rooms / tournaments
- Casino cashback
- Advanced stats
- Visual effects

## 12) Kazino (private)

Menyu:

- Mines
- Blackjack
- Roulette
- Dice
- Basketbol
- Futbol
- Tarix

Umumiy qoida:

- Chance ochiq ko‘rsatilmaydi
- Bet summasini user yozadi

### Mines

Flow: bet → mina soni → grid → tanlash → cashout.

- Mina ko‘paygan sari koeffitsient oshadi
- Mina bosilsa yutqazish
- Cashout bo‘lsa joriy multipler bo‘yicha chiqish

### Blackjack

Flow: bet → kartalar → Hit/Stand → hisob.

- 21 dan oshsa lose
- Blackjack uchun alohida payout bo‘lishi mumkin

### Roulette

Flow: bet → (Red/Black/0) → natija.

- Red/Black oddiy payout
- 0 yuqori payout

### Telegram game’lar

- 🎲, 🏀, ⚽ uchun payout (masalan 3x) owner panel orqali boshqariladi.

### Tarix

Har user uchun:

- O‘yin turi
- Bet
- Win/Lose
- To‘lov/yutuq qiymati

### Kazino sozlamalari (owner/admin)

- Mines multipliers
- Min/max bet
- Mine count limiti
- Blackjack/Roulette payout
- Dice/Basket/Futbol payout
- Casino ON/OFF

## 13) Staff modeli

### Support

- Ticket/report/payment issue
- Stuck game’ni adminlarga eskalatsiya qiladi

### Admin

- Moderatsiya (ban/mute va h.k.)
- Suspicious user review
- Active games monitoring
- Stats/users/groups ko‘rish
- Economy admin operatsiyalari

### Partner

Talablar (namunaviy):

- Bot guruhda bo‘lishi
- Yetarli a’zo va aktivlik
- Past farm riski

Imkoniyatlar:

- O‘z guruhida `/stop`, `/ginfo`
- Community analytics / tournament yordamchi imkoniyatlari

### Owner

To‘liq root boshqaruv:

- Staff vakolatlari
- Shop narxlari
- Start/shop matnlari
- Kanal/linklar
- Premium/kazino/anti-farm
- Phase media
- Role textlar / kill textlar

## 14) Admin panel

Admin va owner ko‘radi. Tugmali bo‘limlar:

- Users
- Groups
- Active games
- Statistics
- Reports/Tickets
- Withdrawals
- Broadcast
- Logs
- Economy overview
- Group info
- Events

## 15) Owner panel

Faqat owner ko‘radi. Bo‘limlar:

- Admin berish/olish
- Owner transfer
- Shop/price settings
- Currency packages
- Buy contact
- Official/news channels
- Start/shop text
- Premium settings
- Casino settings
- Anti-farm settings
- Phase media upload
- Team chat ON/OFF
- Role inactivity texts
- Custom death messages

Qo‘shimcha muhim tugmalar:

- `✏️ Edit Start Message`
- `📢 Change News Channel`
- `👤 Change Buy Contact`

## 16) Phase media

Upload qilinadigan bosqichlar:

- Night
- Morning
- Day
- Court
- Game over

## 17) Team chat bridge

- Don ↔ Mafia
- Komissar ↔ Serjant

Shart:

- Ikkalasi tirik bo‘lsa private bridge ishlaydi
- Owner/admin panel’dan ON/OFF

## 18) Skip qoidasi (night roles)

- Ko‘p tungi rollarda `⏭ O‘tkazib yuborish` mavjud
- **Istisno:** Konchi har tun 3 kondan 1 tasini majburiy tanlaydi

## 19) Konchi mexanikasi

Har tun 3 variantdan biri:

- 1–5 olmos
- 50–250$
- O‘lim

Agar o‘limli variant tushsa:

- Himoya bo‘lsa: tirik qoladi, 1 himoya sarflanadi
- Himoya bo‘lmasa: o‘ladi

## 20) Rollar katalogi

Loyihada keltirilgan rollar (yakuniy ro‘yxat):

Don, Mafia, Komissar Katani, Doktor, Serjant, Janob, Tinch aholi, Daydi,
Kezuvchi, Advokat, Suitsid, Omadli, Bo‘ri, Qotil, Yollanma qotil, Afsungar,
Aferist, Sehrgar, G‘azabkor, Jurnalist, Sotqin, Joker, Admiral, Kimyogar,
Minior, Robin Gud, Fotoparatchi, Ayg‘oqchi, Konchi, Bomj, Kurort, Putana, Maniac.

Har bir rol uchun:

- Night/day actionlar
- Win condition
- Counter/item interaction
- Inactivity fallback alohida spesifikatsiyada yoziladi

## 21) Inactivity textlar

Story uslubida va owner panel’dan tahrirlanadi.

Misollar:

- `Mafia shahardan qochib ketdi`
- `Doktor shaharni tark etdi`

## 22) Kill textlar

Killer turiga qarab matn o‘zgaradi va owner panel’dan boshqariladi.

Misollar:

- Don kill text
- Komissar kill text
- Mafia kill text
- Maniac kill text

## 23) Anti-farm

Shubhali faoliyatda adaptiv cheklovlar:

- Reward pasaytirish
- Transfer fee oshirish
- Casino RTP pasaytirish
- Premium chest sifati pasaytirish
- Seller cluster detection

## 24) Logging / audit

Majburiy loglar:

- money/send/give transferlar
- unmoney/unsend/ungive aralashuvlar
- admin id, target id
- sabab
- vaqt

## 25) Yakuniy maqsad

Bot quyidagilarni barqaror ta’minlashi kerak:

- Group gameplay toza oqim
- Private premium dashboard UX
- Tungi actionlar maxfiyligi
- To‘liq shop + kazino + panel boshqaruvi
- Media/role text/settings’ni owner orqali moslash
- Economy va anti-farm xavfsizligi

---

## Keyingi kengaytirish (v2 tavsiya)

1. Har bir rolning boshqa rollarga qarshi aniq interaktsiya matrix’i.
2. Qaysi item qaysi role action’ni bloklashi/soft-counter jadvali.
3. Shop narxlari (USD/diamond) bo‘yicha to‘liq pricing table.
4. Admin/owner panel uchun screen-by-screen UX flow diagram.
