#!/usr/bin/env node
// Legge il bollettino regionale, individua le zone con allerta (oggi o
// domani diverso da "green") e invia una notifica push mirata solo ai
// cittadini iscritti ai comuni di quelle zone, riusando i tag
// "comune_<nome>" gia' assegnati dal flusso di iscrizione esistente
// dell'app (nessun nuovo tag da introdurre lato client).
//
// Non rimanda la stessa notifica se lo stato della zona (oggi+domani)
// non e' cambiato dall'ultima esecuzione andata a buon fine: lo stato
// viene salvato in STATE_PATH, che il workflow deve ricommittare nel
// repo dopo ogni run.
//
// Uso:
//   node invia_allerte_zona.js              invia davvero (richiede ONESIGNAL_REST_API_KEY)
//   node invia_allerte_zona.js --dry-run     stampa cosa farebbe, senza chiamare OneSignal

const fs = require('fs');
const path = require('path');

const DRY_RUN = process.argv.includes('--dry-run');

// Percorsi relativi alla root del repo che ospita dati_bollettino.json:
// adatta questi due env var nel workflow se la struttura reale del repo
// e' diversa da quella assunta qui.
const BOLLETTINO_PATH = process.env.BOLLETTINO_PATH || path.join(process.cwd(), 'dati_bollettino.json');
const STATE_PATH = process.env.STATE_PATH || path.join(process.cwd(), 'automazioni_state', 'ultimo_stato_zone.json');
const COMUNI_ZONE_PATH = path.join(__dirname, 'comuni_zone.json');

const ONESIGNAL_APP_ID = process.env.ONESIGNAL_APP_ID || '62bb3a88-4267-4b6c-b209-5262c35284f8';
const ONESIGNAL_REST_API_KEY = process.env.ONESIGNAL_REST_API_KEY;

const LIVELLI = {
    green: { nome: 'Verde', emoji: '🟢', allerta: false },
    yellow: { nome: 'Gialla', emoji: '🟡', allerta: true },
    orange: { nome: 'Arancione', emoji: '🟠', allerta: true },
    red: { nome: 'Rossa', emoji: '🔴', allerta: true },
};

function leggiJson(p, fallback) {
    try {
        return JSON.parse(fs.readFileSync(p, 'utf8'));
    } catch (e) {
        if (fallback !== undefined) return fallback;
        throw new Error(`Impossibile leggere ${p}: ${e.message}`);
    }
}

function scriviStato(p, stato) {
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.writeFileSync(p, JSON.stringify(stato, null, 2) + '\n');
}

function tagComune(comune) {
    return 'comune_' + comune.replace(/\s+/g, '_').toLowerCase();
}

// Costruisce il filtro OneSignal: OR fra tutti i tag comune_X della zona.
// NOTA: la sintassi filters con operator "OR" e' quella documentata da
// OneSignal per combinare piu' condizioni sullo stesso livello (nessun
// raggruppamento/parentesi disponibile nell'API). Non testata con un
// invio reale in questa sessione per non rischiare di notificare
// iscritti veri: verificala con "Send to Test Device" dal pannello
// OneSignal prima di affidarti in produzione.
function costruisciFiltri(comuni) {
    const filters = [];
    comuni.forEach((c, i) => {
        if (i > 0) filters.push({ operator: 'OR' });
        filters.push({ field: 'tag', key: tagComune(c), relation: '=', value: 'true' });
    });
    return filters;
}

async function inviaNotificaZona(zonaNome, comuni, titolo, testo) {
    const payload = {
        app_id: ONESIGNAL_APP_ID,
        filters: costruisciFiltri(comuni),
        headings: { it: titolo, en: titolo },
        contents: { it: testo, en: testo },
        url: 'https://www.formazionesicurezza.org/protezionecivile/bollettino/index.html?view=map',
    };

    if (DRY_RUN) {
        console.log(`--- [DRY RUN] ${zonaNome} ---`);
        console.log('Comuni coinvolti (' + comuni.length + '):', comuni.join(', '));
        console.log('Titolo:', titolo);
        console.log('Testo:', testo);
        return { ok: true };
    }

    if (!ONESIGNAL_REST_API_KEY) {
        throw new Error('ONESIGNAL_REST_API_KEY non impostata (va passata come secret del workflow)');
    }

    const res = await fetch('https://onesignal.com/api/v1/notifications', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json; charset=utf-8',
            Authorization: 'Key ' + ONESIGNAL_REST_API_KEY,
        },
        body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
        console.error(`Errore OneSignal per ${zonaNome}:`, JSON.stringify(data));
        return { ok: false };
    }
    console.log(`Notifica inviata per ${zonaNome} - id: ${data.id}, destinatari stimati: ${data.recipients}`);
    return { ok: true };
}

async function main() {
    const bollettino = leggiJson(BOLLETTINO_PATH);
    const comuniZona = leggiJson(COMUNI_ZONE_PATH);
    const statoPrecedente = leggiJson(STATE_PATH, {});

    const comuniPerZona = {};
    for (const [comune, zona] of Object.entries(comuniZona)) {
        (comuniPerZona[zona] = comuniPerZona[zona] || []).push(comune);
    }

    const nuovoStato = { ...statoPrecedente };
    let inviate = 0;
    let saltate = 0;

    for (const [zona, info] of Object.entries(bollettino.zone || {})) {
        const oggi = LIVELLI[info.oggi] || { nome: info.oggi, emoji: '⚪', allerta: false };
        const domani = LIVELLI[info.domani] || { nome: info.domani, emoji: '⚪', allerta: false };
        const inAllerta = oggi.allerta || domani.allerta;

        if (!inAllerta) {
            // Zona verde: aggiorna lo stato (cosi' un futuro peggioramento
            // viene notificato) ma non manda nulla.
            nuovoStato[zona] = { oggi: info.oggi, domani: info.domani };
            continue;
        }

        const chiaveStato = `${info.oggi}|${info.domani}`;
        const precedente = statoPrecedente[zona];
        const giaNotificata = precedente && `${precedente.oggi}|${precedente.domani}` === chiaveStato;

        if (giaNotificata) {
            console.log(`Zona ${zona}: stato invariato dall'ultima notifica (${chiaveStato}), salto.`);
            saltate++;
            continue;
        }

        const comuni = comuniPerZona[zona] || [];
        if (comuni.length === 0) {
            console.warn(`Zona ${zona} non ha comuni mappati in comuni_zone.json, salto.`);
            continue;
        }

        const titolo = `Allerta ${oggi.nome} - ${zona.replace('BASI ', 'Zona ')}`;
        let testo = `${oggi.emoji} Oggi: ${info.rischio_oggi || oggi.nome}.`;
        if (info.domani !== info.oggi) {
            testo += ` ${domani.emoji} Domani: ${info.rischio_domani || domani.nome}.`;
        }

        const esito = await inviaNotificaZona(zona, comuni, titolo, testo);
        if (esito.ok) {
            nuovoStato[zona] = { oggi: info.oggi, domani: info.domani };
            inviate++;
        }
    }

    if (!DRY_RUN) {
        scriviStato(STATE_PATH, nuovoStato);
    }
    console.log(`${inviate} notifiche inviate, ${saltate} saltate (stato invariato).${DRY_RUN ? ' [DRY RUN: nessun invio reale, stato non salvato]' : ''}`);
}

main().catch((e) => {
    console.error('Errore nello script allerte zona:', e);
    process.exit(1);
});
