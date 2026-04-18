# UtopiaMafiaBot (full interactive foundation)

Bu versiya siz aytgan 3 ta asosiy yo'nalishni kodga olib kirdi:

1. **Full Role Engine metadata + dynamic role action UI**
2. **Owner/Admin panel screen-by-screen interactive flow**
3. **Item/Counter Engine (auto-trigger + priority order)**

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN="..."
export OWNER_ID="..."
python main.py
```

Yoki tez usul:

```bash
cp .env.sample .env
# .env ichiga BOT_TOKEN va OWNER_ID yozing
./run.sh
```

## Yangi imkoniyatlar

### Role Engine
- `/roleengine` — barcha rollar team/goal/ui
- `/rolecard <RoleName>` — bitta rol karta
- `/nightui <chat_id>` — private chatda role asosida button UI
- callback orqali mode/target tanlash (`ract:*`)

### Game Mechanics
- `/newgame` lobby + inline join
- `/startgame` random role assign
- `/myrole <chat_id>` private role
- `/action <chat_id> <...>` command mode
- `/nextphase` phase resolver
- `/vote` day voting

### Item/Counter Engine
Priority:
1) himoya
2) qotildan_himoya
3) doridan_himoya
4) sirpanishdan_himoya
5) osishdan_himoya

- auto-trigger defensive pipeline
- `/itemtoggle <item> <on|off>`

### Admin/Owner Panel
- `/start` -> role-based visibility
- `👑 Admin Panel` (admin + owner)
- `⚙️ Owner Panel` (owner only)
- sub-screens for users/groups/games/logs/economy
- owner flows: shop/price/channels/casino/game/anti-farm/media/role-texts

### Casino
- `/dicebet`, `/roulette`, `/blackjack`, `/mines`, `/chistory`
- owner tuning via `/setcasino`
- bet limits by level:
  - Beginner: 10..200
  - Normal: 50..1000
  - VIP: 100..5000
- target RTP settings:
  - mines=0.92, blackjack=0.96, roulette=0.94, telegram=0.90

### Settings
- `/setting get <key>`
- `/setting set <key> <value>`
- `/broadcast <text>` (admin/owner)
- `/help` yoki `/helpme`

## Test

```bash
python -m unittest -q
```

## Eslatma
Bu hali ham production final emas, lekin endi foundation ancha to'liq:
- interactive role system
- button-based gameplay
- dynamic role actions
- priority order: block -> modify -> check -> trap -> kill -> defense -> status -> heal -> random
