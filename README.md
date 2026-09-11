# 🎯 PikadoBro

**Trenutna testna verzija: v0.32 TEST**

🇬🇧 **English:** [Open README_EN.md](README_EN.md)

**PikadoBro** (u engleskom sučelju **DartsBro**) je jednostavan darts trener za jednog igrača, napravljen za stvarni trening pred pločom — bez nepotrebnih menija, reklama i distrakcija.

Radi u browseru i kao PWA, prilagođen je mobitelu, tabletu i desktopu, a podaci o treningu ostaju lokalno na uređaju.

## Igre

- **X01** — 301 / 501 / 701 / 901 / 1001, Double Out ili Master Out
- **High Score** — 7 / 8 / 15 rundi
- **Split Score** i **Split Score Back**
- **Round the World** — Singles / Doubles / Triples + opcionalni Bull
- **Checkout Trainer** — PDC / Random / Manual / Crazy
- **Checkout Challenge** — 2 Dart / 3 Dart Finishes s preporučenim checkout rutama
- **Speed Game** — Easy 60 s / Normal 40 s / Pro 30 s / King 25 s; trening traje 5 minuta
- **Bob's 27**
- **Popravak** (EN: FixTheThing) — Ručno / Automatski, fokusirani trening jedne mete

## Kako se koristi

Odaberi igru, podesi trening i baci strelice. PikadoBro ne pokušava igrati umjesto tebe — rezultat unosiš ručno, a aplikacija vodi tijek igre i statistiku.

Tijekom aktivne igre sučelje je namjerno minimalno. **Dvostruki klik / double-tap na prazni dio ekrana** otvara izbornik za nastavak, Undo, restart, završetak igre i povratak na početnu.

Detaljna pravila pojedinih treninga nalaze se u [MANUAL.md](MANUAL.md). Kratke napomene za testere su u [TESTING.md](TESTING.md).

English game manual: [MANUAL_EN.md](MANUAL_EN.md).

## Popravak

Ručno način podržava 1–20, D1–D20, T1–T20, Bull i DBull. Sesija traje 10 rundi / 30 strelica i bilježi stvarni pogodak svake strelice. Za brži unos prikazuje kratice za ciljanu metu i susjedne brojeve na ploči. Tijekom treninga nema live postotka — fokus ostaje na bacanju, a rezultat i statistika prikazuju se na kraju.

Automatski koristi dovoljno pouzdane podatke iz treninga i predlaže mete koje traže dodatni rad. Ne koristi X01 ukupne scoreove za zaključivanje gdje je pojedina strelica završila.

**Moj trening (AI Mode beta)** nalazi se unutar Popravka. Nudi workout od 10 / 15 / 20 / 30 / 45 minuta. Workout može kombinirati mete iz Popravka i cijele discipline, npr. X01 301 DO, High Score, Split Score / Back, Round the World, Bob's 27, Checkout Trainer ili Speed Game. Plan je uvijek vidljiv i editabilan te ga igrač mora potvrditi prije početka. PikadoBro može predložiti početni miks i, kad ima dovoljno statistike, dati prednost slabijim metama. Maksimalno planirano trajanje je 45 minuta.

## Statistika i backup

PikadoBro prikazuje statistiku po disciplinama. Podaci ostaju lokalno u pregledniku. Ugrađeni **JSON Backup / Restore** služi za sigurnosnu kopiju ili prijenos PikadoBro podataka.

## Jezik i uređaji

Sučelje podržava **hrvatski i engleski**. Dizajnirano je prvenstveno za touch uređaje, ali normalno radi i na desktopu. Može se instalirati kao PWA na podržanim mobilnim uređajima.

## Status

**Test build v0.29.** Sve gore navedene discipline su aktivne. PikadoBro je još u aktivnom razvoju; pravila, statistika i UX testiraju se kroz stvarne treninge pa se detalji mogu mijenjati između verzija.


## Podrži razvoj

Kod, aplikacija i ideja ponuđeni su besplatno. Ako ti se PikadoBro sviđa i pomaže u treningu, možeš autoru ubaciti koji EUR za pivu ili whisk(e)y ❤️ — možda tako nastane još koja dobra ideja.

**Revolut:** https://revolut.me/@ivan50ba6

### Privatnost i brisanje podataka

PikadoBro sprema podatke lokalno na uređaju. U **Podaci / Backup** postoji opcija **Obriši sve lokalne podatke** koja trajno briše statistiku, treninge, postavke i aktivnu igru. PWA/aplikacija ostaje instalirana dok je korisnik sam ne ukloni.

### Prilagodljiv gameplay ekran

v0.32 prilagođava aktivnu igru stvarnoj visini i širini ekrana. Na mobitelima su quick-score tipke složene kompaktnije, a keypad i UNDO ostaju unutar vidljivog prozora kako bi se smanjilo slučajno scrollanje tijekom bacanja.

### v0.32 provjereni bugfixevi

Uz responsive gameplay iz v0.31, v0.32 ispravlja Master Out bust na preostalih 1, Resume oznake za Speed Game i Checkout Challenge, zaustavljanje timera pri povratku na Početnu, oznaku verzije u JSON backupu, HR/EN naziv backup datoteke, povrat aktivne igre nakon restorea i zatvaranje AudioContexta nakon Crazy beepa.
