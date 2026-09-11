# PikadoBro — kratke upute za igre

🇬🇧 **English:** [MANUAL_EN.md](MANUAL_EN.md)

## X01

Odaberi **301, 501, 701, 901 ili 1001** te Double Out ili Master Out. Nakon svake runde upiši ukupan rezultat tri strelice. Bust vraća score na stanje prije te runde.

Kad remaining padne na **60 ili manje**, PikadoBro automatski prati checkout fazu. Od **61 do 170** možeš označiti **POKUŠAJ IZLAZA** ako taj visit stvarno igraš kao checkout. Kod završenog lega aplikacija pita kojom si strelicom izašao.

Maksimalan broj rundi je: 301 = 10, 501 = 15, 701 = 18, 901 = 21, 1001 = 24.

## High Score

Odaberi **7, 8 ili 15 rundi**. U svakoj rundi upiši zbroj tri strelice. Cilj je napraviti što veći ukupni score.

## Split Score

Počinješ sa **40 bodova**. Mete su:

`15 → 16 → Double → 17 → 18 → Triple → 19 → 20 → Bull`

Kod brojčanih meta unosi se broj pogodaka/vrijednost pogodaka u ciljanu metu, a kod Double/Triple runde osvojeni bodovi. Ako sa sve tri strelice potpuno promašiš zadanu metu, trenutni score se prepolovi. Kod neparnog broja zaokružuje se u korist igrača, npr. **75 → 38**.

**Split Score Back** koristi ista pravila obrnutim redoslijedom.

## Round the World

Odaberi **Singles, Doubles ili Triples** i prolazi mete od 1 do 20. Imaš najviše **40 rundi**.

Upisuješ koliko je od tri strelice pogodilo točan traženi prsten. Ako upišeš **0**, ostaješ na istoj meti. Ako pogodiš 1, 2 ili 3 puta, prelaziš na sljedeći broj.

Opcionalni završni Bull ovisi o modu: Singles traži **Bull 25**, Doubles traži **DB 50**, a Triples prihvaća **Bull 25 ili DB 50**.

## Checkout Trainer

Checkout Trainer je vježba izlaza; promašaj ne prekida trening. Trening možeš ograničiti brojem rundi ili vremenom.

- **PDC** — vrti standardne mete: 40, 32, 36, 50, 20, 8, 4, 16 i 24.
- **Random** — nasumične mete 2–40.
- **Manual** — sam upisuješ mete koje želiš vrtjeti kroz trening.
- **Crazy** — vrti parne checkout mete i automatski ih mijenja nakon nasumičnih 5–15 sekundi uz zvučni signal.

Za svaku rundu označi **IZLAZ** ili **PROMAŠAJ**. PikadoBro broji runde, pogotke, promašaje i checkout postotak.

## Checkout Challenge

Checkout Challenge je progresivni trening checkout ruta s preporučenim izlazima.

### 2 Dart Finishes

Ideš redom kroz moguće izlaze od 2 do 100. Trenutnu metu moraš završiti prije prelaska na sljedeću. Brojevi koji se ne mogu završiti u dvije strelice preskaču se.

### 3 Dart Finishes

Ideš kroz moguće izlaze od 99 do 170. Broj 100 pripada 2 Dart disciplini, a standardni bogey brojevi se preskaču.

PikadoBro prikazuje preporučenu praktičnu rutu i, gdje ima smisla, još jednu razumnu alternativu. Namjerno ne prikazuje egzotične rute koje su matematički moguće, ali nisu dobar izbor za trening.

Upisuješ samo **IZLAZ** ili **PROMAŠAJ**. Promašaj te ostavlja na istoj meti. Napredak se automatski sprema. **NOVI CIKLUS** kreće ispočetka, ali čuva povijest prethodnih ciklusa za usporedbu. Povijest se briše zasebno.

## Bob's 27

Počinješ s **27 bodova** i redom gađaš D1, D2 ... D20 pa Bull. Na svakoj meti imaš tri strelice.

Ako pogodiš double, dodaje se njegova vrijednost za svaki pogodak. Ako sva tri puta promašiš, vrijednost tog doublea se oduzima. Ako score padne na **0 ili manje**, igra završava.

## Undo i izbornik

**Undo vraća samo posljednji uneseni visit i može se koristiti samo jednom.** Nakon Undo-a nije moguće nastaviti vraćati starije rezultate; novi Undo postaje dostupan tek nakon novog unosa.

Tijekom igre dvostruki klik ili double-tap na prazni dio ekrana otvara skriveni izbornik.


## Checkout Challenge — 2 Dart / 3 Dart Finishes

Checkout Challenge je progresivni trening izlaza s prikazanim rutama.

- **2 Dart Finishes:** prolazi kroz sve scoreove od 2 do 100 koji se mogu zatvoriti u najviše dvije strelice. Neparni izlazi su uključeni; scoreovi koji nisu mogući u dvije strelice automatski se preskaču.
- **3 Dart Finishes:** prolazi kroz validne checkoutove 99–170 koji se mogu zatvoriti u najviše tri strelice. Bogey brojevi se preskaču.
- Ispod mete PikadoBro prikazuje preporučenu rutu i do dvije alternative.
- **PROMAŠAJ** ostavlja igrača na istoj meti. Uspješan izlaz označava se brojem iskorištenih strelica.
- Napredak se automatski sprema. **Novi ciklus** kreće od početka, ali čuva stare cikluse radi usporedbe napretka. Povijest se može zasebno obrisati.


### Checkout Challenge v0.12
Prikazuje preporučenu checkout rutu. U treningu se bilježi samo **IZLAZ** ili **PROMAŠAJ**; broj strelica se ne traži. Promašaj ostavlja igrača na istoj meti. Standardne rute imaju prednost pred matematički mogućim, ali nepraktičnim kombinacijama.

## Speed Game
Brzinski trening pod pritiskom. Ukupni trening traje najviše 5 minuta. Svaka meta ima vlastiti timer: Easy 60 s (1–60), Normal 40 s (1–100), Pro 30 s (1–180), King 25 s. Ako vrijeme za metu istekne, bilježi se promašaj i odmah dolazi nova meta. Pogodak ili ručni promašaj također odmah pokreću novu metu. King uvijek traži 150 kao **DB · DB · DB**; tijekom pet minuta možeš napraviti više King pokušaja. PikadoBro prati pokušaje, pogodak %, timeoute, najbolji niz i prosječno vrijeme uspješnog pogotka.


## Statistika i Backup / Restore

Na početnom ekranu otvori **Statistika** za ukupne rezultate po disciplinama. **Backup / Restore** izvozi sve lokalne PikadoBro podatke u JSON datoteku ili ih vraća iz ranije spremljenog backupa. Restore zamjenjuje postojeće PikadoBro podatke.

## Popravak

**Ručno:** odaberi metu (1–20, D1–D20, T1–T20, Bull ili DBull) i odigraj 10 rundi / 30 strelica. Svaku strelicu upiši točno onako kako je završila. `0` je potpuni promašaj/felga. Za double ili triple možeš prvo odabrati D ili T pa broj; Bull i DBull imaju direktne tipke.

Ako je meta običan broj, svaki prsten tog broja vrijedi kao jedan pogodak. Primjerice, za metu 20 su S20, D20 i T20 svi pogodak. Ako treniraš D20 ili T20, samo taj točan prsten računa se kao pogodak.

Za brži unos aktivni ekran nudi direktne kratice za odabranu metu i njezina dva fizička susjeda na standardnoj dart ploči. Puna tipkovnica ostaje dostupna za svaki drugi pogodak. Tijekom treninga nema live broja pogodaka ni postotka — ekran kaže **KONCENTRIRAJ SE!**, a rezultat i statistika prikazuju se tek na kraju.

**Automatski:** PikadoBro traži slabe mete u kompatibilnim statistikama treninga. Otključava se nakon najmanje 10 relevantnih sesija, a kandidat mora imati najmanje 15 evidentiranih strelica. Dok nema dovoljno podataka, gumb za pokretanje se ne prikazuje. X01 ukupne scoreove ne koristi za zaključivanje gdje je pojedina strelica završila jer ti podaci nisu dovoljno precizni.

### Moj trening / AI Mode beta

Nalazi se unutar Popravka. Odaberi 10, 15, 20, 30 ili 45 minuta. Workout može kombinirati mete iz Popravka i cijele discipline. Primjer: Popravak 20 → X01 301 Double Out → Popravak Bull → Split Score Back. Svaki blok možeš promijeniti, maknuti ili dodati prije početka, a plan se pokreće tek nakon tvoje potvrde. Ako postoji dovoljno pouzdane statistike, PikadoBro daje prednost slabijim metama; bez statistike nudi gotovi uravnoteženi miks. Maksimalno planirano trajanje workouta je 45 minuta.

## Podaci / Backup

Uz JSON backup i restore, opcija **Obriši sve lokalne podatke** briše sve PikadoBro podatke spremljene na uređaju. Brisanje se mora dodatno potvrditi i ne može se poništiti.
