# O ovom projektu

ClusterSizer je nastao iz jednog konkretnog, dosadnog problema: sysadmin
sastavlja HW za novi cluster, pa mora ručno zbrajati CPU, RAM, storage i
mrežne portove u Excelu, po treći put te godine, i svaki put ispočetka.

Alat je napravljen u suradnji čovjeka i AI-a (Claude, Anthropic) - i
namjerno to ne skrivamo, jer mislimo da je to danas normalan način rada, a
ne nešto što treba zamagliti sitnim printom.

Podjela je otprilike ovakva: ideja, zahtjevi, sysadmin logika ("DR-ovi
često nisu 1:1 replicirani", "treba ctrl+klik za multi-select", "nemoj
dopustiti da netko slučajno uveze VM-ove pod servere") - to je sve došlo od
čovjeka koji stvarno radi ovaj posao. Arhitektura koda, pisanje samog
Pythona/Qt-a, testiranje i deblertanje - to je uglavnom AI, uz čovjeka koji
je svaki korak pregledao, tražio popravke i odbijao ono što ne valja.

Nijedna strana ovdje ne zaslužuje svu zaslugu, pa je ni ne uzima. Alat je
javan i besplatan upravo zato da bude koristan drugima koji rješavaju isti
dosadni problem - a ne kao demonstracija bilo čega.

Ako naiđeš na bug ili imaš ideju za v3 - issue/PR su dobrodošli.

---

*ClusterSizer was built through human-AI collaboration (Claude, Anthropic).
The requirements and domain knowledge (what actually matters when sizing a
cluster, what a sysadmin needs day to day) came from a human who does this
job. The code architecture and implementation were largely AI-written, with
every step reviewed, tested, and corrected by a human. It's released free
and open because it solves a real, boring problem - not as a demo of
anything.*
