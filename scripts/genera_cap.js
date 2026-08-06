#!/usr/bin/env node
// Genera un feed CAP 1.2 (OASIS "Common Alerting Protocol") a partire dal
// bollettino di criticita' regionale (dati_bollettino.json), cosi' che il
// dato possa essere consumato da soggetti terzi (aggregatori CAP generici,
// Google Public Alerts, Home Assistant, e in prospettiva MeteoAlarm) con
// provenienza verificabile invece che solo dal widget/JSON pensati per il
// nostro front-end.
//
// NOTA REALISTICA: MeteoAlarm aggrega solo i servizi meteorologici nazionali
// ufficiali tramite un accordo EUMETNET - un feed autopubblicato non viene
// ingerito automaticamente. Questo script produce comunque un feed CAP+Atom
// corretto, firmato e verificabile in modo indipendente, utilizzabile da
// qualunque consumer CAP generico; un'eventuale adozione da MeteoAlarm
// richiedera' in futuro un canale formale (Regione <-> EUMETNET).
//
// Ambito v1: solo il bollettino di criticita' di zona (7 zone). Gli avvisi
// comunali ad hoc (avvisi_comunali.json / salva_avviso.php) restano fuori.
//
// Pattern ripreso da invia_allerte_zona.js (stesso stile: env var con
// default, --dry-run, diff di stato contro un file committato dal
// workflow), ma con uno stato piu' ricco perche' CAP richiede identificativi
// permanenti e una catena Alert -> Update -> Cancel tracciabile via
// <references>, non solo un dedup sul colore.
//
// Uso:
//   node genera_cap.js              genera davvero (richiede CAP_SIGNING_PRIVATE_KEY per firmare)
//   node genera_cap.js --dry-run    stampa cosa farebbe, non scrive nulla
//
// Questo script vive in questo repo ma e' pensato per essere eseguito dal
// workflow GitHub Actions ESTERNO (repo Eatapples15/allerte_bollettino_basilicata)
// che gia' esegue invia_allerte_zona.js - quel workflow non e' presente qui,
// quindi le modifiche li' vanno fatte a parte:
//   - "npm install xml-crypto" prima di invocare questo script (dipendenza
//     usata solo per la firma XML-DSig: niente canonicalizzazione scritta a mano);
//   - nuovi secret CAP_SIGNING_PRIVATE_KEY (+ CAP_SIGNING_CERT, vedi sotto);
//   - commit/pubblicazione delle nuove cartelle cap/ e automazioni_state/cap_stato_zone.json,
//     esattamente come gia' avviene oggi per automazioni_state/ultimo_stato_zone.json.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DRY_RUN = process.argv.includes('--dry-run');

// Percorsi che dipendono dalla cwd del workflow esterno (dove vive
// dati_bollettino.json), stesso schema di invia_allerte_zona.js.
const BOLLETTINO_PATH = process.env.BOLLETTINO_PATH || path.join(process.cwd(), 'dati_bollettino.json');
const CAP_STATE_PATH = process.env.CAP_STATE_PATH || path.join(process.cwd(), 'automazioni_state', 'cap_stato_zone.json');
const CAP_OUTPUT_DIR = process.env.CAP_OUTPUT_DIR || path.join(process.cwd(), 'cap');

// File propri di questo repo: percorso fisso relativo a __dirname, come
// COMUNI_ZONE_PATH nello script gemello (non serve renderli configurabili,
// non dipendono dalla cwd del workflow esterno).
const COMUNI_ZONE_PATH = path.join(__dirname, 'comuni_zone.json');
const GEOJSON_PATH = path.join(__dirname, '..', 'limits_R_17_municipalities.geojson');
const AWARENESS_TYPES_PATH = path.join(__dirname, 'cap_awareness_types.json');

// Identita' e destinazioni pubblicate nel feed.
const CAP_SENDER = process.env.CAP_SENDER || 'cap-sicurbas@formazionesicurezza.org';
const CAP_SENDER_NAME = process.env.CAP_SENDER_NAME
    || "SicurBas - ripubblicazione non ufficiale del Bollettino di Criticita', Regione Basilicata";
const CAP_WEB_URL = process.env.CAP_WEB_URL
    || 'https://www.formazionesicurezza.org/protezionecivile/bollettino/index.html?view=map';
// Base pubblica dove il repo esterno pubblica cap/ via GitHub Pages, accanto
// a dati_bollettino.json - usata solo per costruire <id>/<link rel="self"> dell'Atom.
const CAP_FEED_BASE_URL = process.env.CAP_FEED_BASE_URL
    || 'https://eatapples15.github.io/allerte_bollettino_basilicata/cap';

// Firma XML-DSig: usiamo un certificato X.509 (anche autofirmato) invece di
// una chiave RSA "nuda", perche' xml-crypto genera nativamente un <KeyInfo>
// con <X509Certificate> da un publicCert, mentre incorporare una RSAKeyValue
// grezza richiederebbe codice su misura. Un certificato autofirmato oggi si
// sostituisce domani con uno emesso da una CA reale senza cambiare nessun'altra
// parte del meccanismo (stessa forma di KeyInfo).
const CAP_SIGNING_PRIVATE_KEY = process.env.CAP_SIGNING_PRIVATE_KEY || null;
const CAP_SIGNING_CERT = process.env.CAP_SIGNING_CERT || null;
const CAP_SIGNING_KEY_ID = process.env.CAP_SIGNING_KEY_ID || 'v1';

// Per quante ore un alert Cancel resta elencato in index.atom dopo la
// cessazione (il file XML dell'alert non viene MAI rimosso, solo la riga
// nell'indice) - 24-48h e' la finestra raccomandata dal profilo aggregator
// CAP-Feeds v1.0 di OASIS.
const CAP_RETENTION_HOURS = parseInt(process.env.CAP_RETENTION_HOURS || '48', 10);

// Tabella CAP per livello. green non genera mai un nuovo Alert/Update (CAP
// non ha un valore di severity per "nessun rischio"): una zona verde con uno
// stato precedente attivo genera invece un Cancel (vedi elaboraZona).
const LIVELLO_CAP = {
    yellow: { severity: 'Moderate', responseType: 'Monitor', headline: "Criticita' Ordinaria", awarenessLevel: '2; yellow; Moderate' },
    orange: { severity: 'Severe', responseType: 'Prepare', headline: "Criticita' Moderata", awarenessLevel: '3; orange; Severe' },
    red: { severity: 'Extreme', responseType: 'Shelter', headline: "Criticita' Elevata", awarenessLevel: '4; red; Extreme' },
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

function escapeXml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
}

// --- Normalizzazione nomi comune e lettura del geojson -----------------

// comuni_zone.json e limits_R_17_municipalities.geojson gestiscono gli
// apostrofi dei nomi composti in modo incoerente ("Sant'Andrea" -> "SANT
// ANDREA" con uno spazio, "d'Agri" -> "DAGRI" senza alcun separatore):
// rimuovere ogni carattere non alfanumerico (non solo spazi/apostrofi) e'
// l'unica normalizzazione verificata che dia un match pulito su tutti i 131 comuni.
function normalizzaNomeComune(nome) {
    return nome
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, '');
}

function costruisciIndiceGeojson(geojsonPath) {
    const geojson = leggiJson(geojsonPath);
    const indice = new Map();
    for (const feature of geojson.features) {
        indice.set(normalizzaNomeComune(feature.properties.name), feature);
    }
    return indice;
}

function ringToCapPolygon(ring) {
    // CAP vuole coppie "lat,lon" separate da spazio, anello chiuso; il
    // geojson da' [lon,lat] e non garantisce che l'anello sia gia' chiuso.
    const punti = ring.map(([lon, lat]) => `${lat.toFixed(5)},${lon.toFixed(5)}`);
    if (punti.length && punti[0] !== punti[punti.length - 1]) punti.push(punti[0]);
    return punti.join(' ');
}

function geometriaToCapPoligoni(geometry) {
    if (geometry.type === 'Polygon') {
        // Si usa solo l'anello esterno (coordinates[0]): CAP non ha un
        // concetto di "buco" nei poligoni. Un solo comune (San Fele) ha un
        // anello interno nel dataset attuale: semplificazione dichiarata,
        // impatto trascurabile su un'area di allerta amministrativa.
        return [ringToCapPolygon(geometry.coordinates[0])];
    }
    if (geometry.type === 'MultiPolygon') {
        // 9 comuni nel dataset attuale sono MultiPolygon: un <polygon> per
        // ogni sotto-poligono e' il costrutto CAP standard (piu' <polygon>
        // per <area> sono esplicitamente ammessi).
        return geometry.coordinates.map(poly => ringToCapPolygon(poly[0]));
    }
    return [];
}

function costruisciArea(zonaNome, comuni, geoIndice) {
    const poligoni = [];
    const geocodes = [];
    const comuniTrovati = [];
    for (const comune of comuni) {
        const feature = geoIndice.get(normalizzaNomeComune(comune));
        if (!feature) {
            console.warn(`Comune "${comune}" (zona ${zonaNome}) non trovato nel geojson: geometria/ISTAT omessi per questo comune.`);
            continue;
        }
        comuniTrovati.push(comune);
        if (feature.properties.com_istat_code) geocodes.push(feature.properties.com_istat_code);
        poligoni.push(...geometriaToCapPoligoni(feature.geometry));
    }
    return {
        areaDesc: `Zona di allerta ${zonaNome} (Regione Basilicata): ${comuniTrovati.join(', ')}`,
        poligoni,
        geocodes,
    };
}

function costruisciAreaXml(area) {
    const poligoniXml = area.poligoni.map(p => `        <polygon>${p}</polygon>`).join('\n');
    const geocodesXml = area.geocodes
        .map(g => `        <geocode><valueName>ISTAT</valueName><value>${escapeXml(g)}</value></geocode>`)
        .join('\n');
    return `      <area>
        <areaDesc>${escapeXml(area.areaDesc)}</areaDesc>
${poligoniXml}
${geocodesXml}
      </area>`;
}

// --- Date/ora: stringhe italiane -> CAP dateTime con offset Europe/Rome --

function parseOraDel(str) {
    const m = /ore\s+(\d{1,2}):(\d{2})\s+del\s+(\d{1,2})\/(\d{1,2})\/(\d{4})/i.exec(str || '');
    if (!m) throw new Error(`Formato data/ora non riconosciuto (atteso "ore HH:MM del DD/MM/YYYY"): "${str}"`);
    return {
        hour: parseInt(m[1], 10), minute: parseInt(m[2], 10),
        day: parseInt(m[3], 10), month: parseInt(m[4], 10), year: parseInt(m[5], 10),
    };
}

// Estrae i campi wall-clock Europe/Rome di un istante reale (usato per il
// timestamp "sent" del messaggio, cioe' adesso).
function campiRomaDaData(data) {
    const parts = new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Europe/Rome',
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', hour12: false,
    }).formatToParts(data);
    const get = tipo => parts.find(p => p.type === tipo).value;
    // Alcune versioni di ICU restituiscono "24" per la mezzanotte con hour12:false.
    const ora = get('hour') === '24' ? 0 : parseInt(get('hour'), 10);
    return {
        year: parseInt(get('year'), 10), month: parseInt(get('month'), 10), day: parseInt(get('day'), 10),
        hour: ora, minute: parseInt(get('minute'), 10),
    };
}

// Calcola l'offset UTC di Europe/Rome (+01:00 CET / +02:00 CEST) per un dato
// istante wall-clock, senza dipendenze esterne di timezone. Costruiamo un
// "istante-stima" con Date.UTC sugli STESSI campi locali, solo per
// interrogare Intl su quale offset si applica in quella data (non e' una
// vera conversione: i campi restano quelli locali di partenza, vedi sotto).
// Rischio noto e accettato: se l'orario ricade proprio nella finestra di
// un cambio ora legale/solare (notte tra sabato e domenica, fine marzo/ottobre),
// la stima potrebbe leggere l'offset del lato sbagliato della transizione.
// I bollettini regionali validano nel pomeriggio/sera (14:00, 23:59), quindi
// il rischio pratico e' trascurabile.
function offsetEuropeRoma(campi) {
    const stima = new Date(Date.UTC(campi.year, campi.month - 1, campi.day, campi.hour, campi.minute));
    const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'Europe/Rome', timeZoneName: 'shortOffset' }).formatToParts(stima);
    const tz = parts.find(p => p.type === 'timeZoneName');
    const m = /GMT([+-])(\d{1,2})(?::(\d{2}))?/.exec((tz && tz.value) || '');
    if (!m) return '+01:00';
    return `${m[1]}${m[2].padStart(2, '0')}:${m[3] || '00'}`;
}

function formatCapDateTime(campi) {
    const offset = offsetEuropeRoma(campi);
    const pad = n => String(n).padStart(2, '0');
    return `${campi.year}-${pad(campi.month)}-${pad(campi.day)}T${pad(campi.hour)}:${pad(campi.minute)}:00${offset}`;
}

// --- Costruzione identificativo, hash di contenuto ----------------------

// Nessuna virgola (<references> unisce sender,identifier,sent con virgole:
// una virgola nell'identifier romperebbe il parsing) ne' due punti (cosi'
// l'identifier e' direttamente utilizzabile come nome-file, senza bisogno di
// una funzione di slug separata). Mai riusato: ogni Alert/Update/Cancel ne
// riceve uno nuovo.
function generaIdentifier(zonaNome, campiSent) {
    const slug = zonaNome.toLowerCase().replace(/\s+/g, '-');
    const pad = n => String(n).padStart(2, '0');
    const compatto = `${campiSent.year}${pad(campiSent.month)}${pad(campiSent.day)}T${pad(campiSent.hour)}${pad(campiSent.minute)}00`;
    const offset = offsetEuropeRoma(campiSent).replace(':', '');
    const rand = crypto.randomBytes(2).toString('hex');
    return `sicurbas-cap-${slug}-${compatto}${offset}-${rand}`;
}

// Copre anche validita_inizio/fine e data_bollettino, non solo i colori:
// a differenza del dedup di invia_allerte_zona.js (solo oggi|domani), qui
// serve, perche' queste stringhe cambiano ad ogni bollettino anche quando il
// colore resta identico due giorni di fila, e onset/expires devono seguirle -
// altrimenti un alert "invariato nel colore" ma con validita' scaduta
// resterebbe pubblicato stantio.
function calcolaContentHash(zonaInfo, bollettino) {
    const payload = JSON.stringify({
        oggi: zonaInfo.oggi, domani: zonaInfo.domani,
        rischio_oggi: zonaInfo.rischio_oggi || '', rischio_domani: zonaInfo.rischio_domani || '',
        validita_inizio: bollettino.validita_inizio, validita_fine: bollettino.validita_fine,
        data_bollettino: bollettino.data_bollettino,
    });
    return 'sha256:' + crypto.createHash('sha256').update(payload).digest('hex');
}

// --- Costruzione XML: <info>, <alert> -----------------------------------

function trovaAwarenessType(rischio, tabella) {
    if (!rischio) return null;
    return tabella[rischio.trim().toLowerCase()] || null;
}

function costruisciDescrizione(giorno, rischio, headline) {
    const etichettaGiorno = giorno === 'oggi' ? 'Oggi' : 'Domani';
    return `${etichettaGiorno}: ${rischio || headline}. Bollettino di criticita' della Protezione Civile, Regione Basilicata.`;
}

function xmlInfoBlock({ giorno, livello, rischio, onsetCampi, effectiveCampi, expiresCampi, zonaLabel, area, awarenessTypes }) {
    const cap = LIVELLO_CAP[livello];
    const urgency = giorno === 'oggi' ? 'Expected' : 'Future';
    const event = (rischio && rischio.trim()) || cap.headline;
    const headline = `${cap.headline} - ${zonaLabel}`;
    const description = costruisciDescrizione(giorno, rischio, cap.headline);
    const awarenessType = trovaAwarenessType(rischio, awarenessTypes);

    return `    <info>
      <language>it-IT</language>
      <category>Met</category>
      <event>${escapeXml(event)}</event>
      <responseType>${cap.responseType}</responseType>
      <urgency>${urgency}</urgency>
      <severity>${cap.severity}</severity>
      <certainty>Likely</certainty>
      <onset>${formatCapDateTime(onsetCampi)}</onset>
      <effective>${formatCapDateTime(effectiveCampi)}</effective>
      <expires>${formatCapDateTime(expiresCampi)}</expires>
      <senderName>${escapeXml(CAP_SENDER_NAME)}</senderName>
      <headline>${escapeXml(headline)}</headline>
      <description>${escapeXml(description)}</description>
      <web>${escapeXml(CAP_WEB_URL)}</web>
      <parameter><valueName>awareness_level</valueName><value>${escapeXml(cap.awarenessLevel)}</value></parameter>
${awarenessType ? `      <parameter><valueName>awareness_type</valueName><value>${escapeXml(awarenessType)}</value></parameter>\n` : ''}${costruisciAreaXml(area)}
    </info>`;
}

function xmlInfoCancel({ zonaLabel, area, sentCampi }) {
    return `    <info>
      <language>it-IT</language>
      <category>Met</category>
      <event>Cessata criticita'</event>
      <responseType>AllClear</responseType>
      <urgency>Past</urgency>
      <severity>Minor</severity>
      <certainty>Observed</certainty>
      <effective>${formatCapDateTime(sentCampi)}</effective>
      <senderName>${escapeXml(CAP_SENDER_NAME)}</senderName>
      <headline>${escapeXml(`Cessata allerta - ${zonaLabel}`)}</headline>
      <description>${escapeXml(`La criticita' precedentemente segnalata per la ${zonaLabel} e' rientrata (bollettino aggiornato).`)}</description>
      <web>${escapeXml(CAP_WEB_URL)}</web>
${costruisciAreaXml(area)}
    </info>`;
}

function xmlAlert({ identifier, sent, status, msgType, references, infoBlocks }) {
    return `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>${escapeXml(identifier)}</identifier>
  <sender>${escapeXml(CAP_SENDER)}</sender>
  <sent>${sent}</sent>
  <status>${status}</status>
  <msgType>${msgType}</msgType>
  <scope>Public</scope>
${references ? `  <references>${escapeXml(references)}</references>\n` : ''}${infoBlocks.join('\n')}
</alert>
`;
}

function costruisciXmlAlertAttivo({ zonaNome, zonaInfo, bollettino, area, identifier, sent, msgType, references, awarenessTypes }) {
    const inizioCampi = parseOraDel(bollettino.validita_inizio);
    const fineCampi = parseOraDel(bollettino.validita_fine);
    const zonaLabel = zonaNome.replace('BASI ', 'Zona ');
    const infoBlocks = [];

    if (zonaInfo.oggi !== 'green') {
        infoBlocks.push(xmlInfoBlock({
            giorno: 'oggi', livello: zonaInfo.oggi, rischio: zonaInfo.rischio_oggi,
            onsetCampi: inizioCampi, effectiveCampi: inizioCampi,
            // Fine giornata di "oggi" = data di validita_inizio, non "+1 giorno"
            // calcolato: la data e' gia' esplicita nella sorgente.
            expiresCampi: { year: inizioCampi.year, month: inizioCampi.month, day: inizioCampi.day, hour: 23, minute: 59 },
            zonaLabel, area, awarenessTypes,
        }));
    }
    if (zonaInfo.domani !== 'green') {
        // Inizio giornata di "domani" = data di validita_fine (gia' esplicita
        // nella sorgente), non "oggi + 1" calcolato a mano.
        const domaniOnsetCampi = { year: fineCampi.year, month: fineCampi.month, day: fineCampi.day, hour: 0, minute: 0 };
        infoBlocks.push(xmlInfoBlock({
            giorno: 'domani', livello: zonaInfo.domani, rischio: zonaInfo.rischio_domani,
            onsetCampi: domaniOnsetCampi, effectiveCampi: domaniOnsetCampi, expiresCampi: fineCampi,
            zonaLabel, area, awarenessTypes,
        }));
    }

    return xmlAlert({ identifier, sent, status: 'Actual', msgType, references, infoBlocks });
}

function costruisciXmlAlertCancel({ zonaNome, area, identifier, sent, references, sentCampi }) {
    const zonaLabel = zonaNome.replace('BASI ', 'Zona ');
    const infoBlocks = [xmlInfoCancel({ zonaLabel, area, sentCampi })];
    return xmlAlert({ identifier, sent, status: 'Actual', msgType: 'Cancel', references, infoBlocks });
}

// --- Firma XML-DSig (enveloped, exc-c14n, rsa-sha256) -------------------
//
// NOTA sulla conformita' rispetto allo XSD CAP 1.2 rigido: per referenziare
// l'elemento <alert> con una xpath, xml-crypto gli aggiunge automaticamente
// un attributo Id (es. Id="_0"), che lo XSD ufficiale di CAP 1.2 non
// dichiara. E' il normale funzionamento della libreria (non esiste, in
// questa versione, un'opzione pubblica per una reference URI="" a documento
// intero senza Id) ed e' un pattern comune in XML-DSig, ma significa che una
// validazione XSD rigorosissima del file FIRMATO puo' segnalare quell'unico
// attributo in piu'. Il contenuto dell'alert e la firma restano entrambi
// corretti e verificabili; per una validazione XSD pura si puo' validare la
// versione non firmata (vedi verifica in fondo al task).
function firmaXml(xml) {
    if (!CAP_SIGNING_PRIVATE_KEY) {
        console.warn('CAP_SIGNING_PRIVATE_KEY non impostata: alert CAP generato NON firmato. '
            + 'Configurala (insieme a CAP_SIGNING_CERT) come secret del workflow per certificare il feed.');
        return { xml, firmato: false };
    }

    let SignedXml;
    try {
        ({ SignedXml } = require('xml-crypto'));
    } catch (e) {
        console.warn(`Modulo "xml-crypto" non disponibile: alert CAP generato NON firmato (${e.message}). `
            + 'Aggiungi "npm install xml-crypto" nel workflow prima di eseguire questo script.');
        return { xml, firmato: false };
    }

    try {
        const sig = new SignedXml({
            privateKey: CAP_SIGNING_PRIVATE_KEY,
            publicCert: CAP_SIGNING_CERT || undefined,
            signatureAlgorithm: 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256',
            canonicalizationAlgorithm: 'http://www.w3.org/2001/10/xml-exc-c14n#',
            getKeyInfoContent: CAP_SIGNING_CERT ? SignedXml.getKeyInfoContent : undefined,
        });
        sig.addReference({
            xpath: "//*[local-name(.)='alert']",
            transforms: ['http://www.w3.org/2000/09/xmldsig#enveloped-signature', 'http://www.w3.org/2001/10/xml-exc-c14n#'],
            digestAlgorithm: 'http://www.w3.org/2001/04/xmlenc#sha256',
        });
        sig.computeSignature(xml);
        return { xml: sig.getSignedXml(), firmato: true };
    } catch (e) {
        console.warn(`Firma XML-DSig fallita per questo alert, pubblicato NON firmato: ${e.message}`);
        return { xml, firmato: false };
    }
}

function pubblicaChiavePubblica(outputDir) {
    if (!CAP_SIGNING_CERT) return;
    const keysDir = path.join(outputDir, 'keys');
    fs.mkdirSync(keysDir, { recursive: true });
    fs.writeFileSync(path.join(keysDir, 'public_cert.pem'), CAP_SIGNING_CERT);
    // Copia archiviata per key id, cosi' dopo una rotazione le firme vecchie restano verificabili.
    fs.writeFileSync(path.join(keysDir, `public_cert.${CAP_SIGNING_KEY_ID}.pem`), CAP_SIGNING_CERT);
    try {
        const cert = new crypto.X509Certificate(CAP_SIGNING_CERT);
        fs.writeFileSync(path.join(keysDir, 'fingerprint.txt'), `${CAP_SIGNING_KEY_ID}: SHA-256 ${cert.fingerprint256}\n`);
    } catch (e) {
        console.warn(`Impossibile calcolare il fingerprint del certificato pubblicato: ${e.message}`);
    }
}

// --- Risoluzione comune -> zona, coi comuni a cavallo di piu' zone -----

const LIVELLO_RANK = { green: 0, yellow: 1, orange: 2, red: 3 };

function livelloPeggiore(zonaInfo) {
    if (!zonaInfo) return 0;
    return Math.max(LIVELLO_RANK[zonaInfo.oggi] ?? 0, LIVELLO_RANK[zonaInfo.domani] ?? 0);
}

// comuni_zone.json mappa la maggior parte dei comuni su una sola zona
// (stringa), ma almeno un comune (FERRANDINA) e' amministrativamente a
// cavallo di due zone di allerta (valore = array). Per non farlo comparire
// nell'<area> di due alert CAP diversi e potenzialmente concorrenti nello
// stesso giorno, lo si assegna alla zona con la criticita' peggiore del
// bollettino corrente (confrontando oggi e domani); a parita' di livello si
// sceglie la prima zona in ordine alfabetico, per un risultato deterministico
// e riproducibile da un run all'altro.
function risolviComuniPerZona(comuniZona, bollettino) {
    const comuniPerZona = {};
    for (const [comune, zona] of Object.entries(comuniZona)) {
        const zoneComune = Array.isArray(zona) ? zona : [zona];
        let zonaScelta = zoneComune[0];
        if (zoneComune.length > 1) {
            zonaScelta = zoneComune.slice().sort().reduce((migliore, z) => (
                livelloPeggiore(bollettino.zone[z]) > livelloPeggiore(bollettino.zone[migliore]) ? z : migliore
            ));
        }
        (comuniPerZona[zonaScelta] = comuniPerZona[zonaScelta] || []).push(comune);
    }
    return comuniPerZona;
}

// --- Stato/ciclo di vita per zona (Alert / Update / Cancel) -------------

function elaboraZona(zonaNome, zonaInfo, bollettino, statoPrec, awarenessTypes, area) {
    const inAllerta = zonaInfo.oggi !== 'green' || zonaInfo.domani !== 'green';
    const contentHash = calcolaContentHash(zonaInfo, bollettino);
    const sentCampi = campiRomaDaData(new Date());
    const sent = formatCapDateTime(sentCampi);

    if (!statoPrec || statoPrec.status === 'cancelled') {
        if (!inAllerta) return { azione: 'nessuna-allerta' };
        const identifier = generaIdentifier(zonaNome, sentCampi);
        const xml = costruisciXmlAlertAttivo({
            zonaNome, zonaInfo, bollettino, area, identifier, sent, msgType: 'Alert', references: null, awarenessTypes,
        });
        return {
            azione: 'alert', identifier, xml,
            nuovoStato: {
                identifier, sender: CAP_SENDER, sent, firstSent: sent,
                status: 'active', msgType: 'Alert', contentHash, cancelledAt: null,
            },
        };
    }

    // statoPrec.status === 'active' da qui in poi.
    if (!inAllerta) {
        const references = `${statoPrec.sender},${statoPrec.identifier},${statoPrec.sent}`;
        const identifier = generaIdentifier(zonaNome, sentCampi);
        const xml = costruisciXmlAlertCancel({ zonaNome, area, identifier, sent, references, sentCampi });
        return {
            azione: 'cancel', identifier, xml,
            nuovoStato: {
                identifier, sender: CAP_SENDER, sent, firstSent: statoPrec.firstSent,
                status: 'cancelled', msgType: 'Cancel', contentHash, cancelledAt: sent,
            },
        };
    }

    if (statoPrec.contentHash === contentHash) {
        return { azione: 'invariato' };
    }

    const references = `${statoPrec.sender},${statoPrec.identifier},${statoPrec.sent}`;
    const identifier = generaIdentifier(zonaNome, sentCampi);
    const xml = costruisciXmlAlertAttivo({
        zonaNome, zonaInfo, bollettino, area, identifier, sent, msgType: 'Update', references, awarenessTypes,
    });
    return {
        azione: 'update', identifier, xml,
        nuovoStato: {
            identifier, sender: CAP_SENDER, sent, firstSent: statoPrec.firstSent,
            status: 'active', msgType: 'Update', contentHash, cancelledAt: null,
        },
    };
}

function scriviAlertFile(outputDir, identifier, xml) {
    const alertsDir = path.join(outputDir, 'alerts');
    fs.mkdirSync(alertsDir, { recursive: true });
    const filePath = path.join(alertsDir, `${identifier}.xml`);
    if (fs.existsSync(filePath)) {
        // Non dovrebbe mai succedere (identifier include timestamp + random),
        // ma un identifier CAP e' permanente: meglio fermarsi che sovrascrivere
        // silenziosamente un alert gia' pubblicato.
        throw new Error(`Collisione di identifier CAP: ${filePath} esiste gia'.`);
    }
    fs.writeFileSync(filePath, xml);
}

// --- Indice Atom ----------------------------------------------------------

function costruisciAtom(statoPerZona) {
    const ora = Date.now();
    const entries = [];
    let aggiornatoMax = null;

    for (const [zonaNome, stato] of Object.entries(statoPerZona)) {
        if (!stato) continue;
        const attivo = stato.status === 'active';
        const cancellatoDiRecente = stato.status === 'cancelled' && stato.cancelledAt
            && (ora - new Date(stato.cancelledAt).getTime()) < CAP_RETENTION_HOURS * 3600 * 1000;
        if (!attivo && !cancellatoDiRecente) continue;

        const zonaLabel = zonaNome.replace('BASI ', 'Zona ');
        const titolo = stato.msgType === 'Cancel' ? `Cessata allerta - ${zonaLabel}` : `Allerta - ${zonaLabel}`;
        if (!aggiornatoMax || stato.sent > aggiornatoMax) aggiornatoMax = stato.sent;

        // Deliberatamente NIENTE elementi cap:-namespaced dentro le entry
        // (solo link + testo breve): e' la raccomandazione normativa del
        // profilo aggregator CAP-Feeds v1.0 di OASIS, per evitare che un
        // consumer tratti una copia parziale/stantia come autorevole.
        entries.push(`  <entry>
    <id>${escapeXml(stato.identifier)}</id>
    <title>${escapeXml(titolo)}</title>
    <updated>${stato.sent}</updated>
    <published>${stato.firstSent}</published>
    <link rel="alternate" type="application/cap+xml" href="alerts/${escapeXml(stato.identifier)}.xml"/>
    <summary>${escapeXml(titolo)} - Bollettino di criticita' Regione Basilicata.</summary>
  </entry>`);
    }

    const feedAggiornato = aggiornatoMax || formatCapDateTime(campiRomaDaData(new Date()));

    return `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>${escapeXml(CAP_FEED_BASE_URL)}/index.atom</id>
  <title>SicurBas - Allerte meteo-idrogeologiche Regione Basilicata (CAP)</title>
  <updated>${feedAggiornato}</updated>
  <author><name>${escapeXml(CAP_SENDER_NAME)}</name></author>
  <link rel="self" href="${escapeXml(CAP_FEED_BASE_URL)}/index.atom"/>
${entries.join('\n')}
</feed>
`;
}

// --- Orchestrazione -------------------------------------------------------

async function main() {
    const bollettino = leggiJson(BOLLETTINO_PATH);
    const comuniZona = leggiJson(COMUNI_ZONE_PATH);
    const geoIndice = costruisciIndiceGeojson(GEOJSON_PATH);
    const awarenessTypes = leggiJson(AWARENESS_TYPES_PATH, {});
    const statoPrecedente = leggiJson(CAP_STATE_PATH, {});

    const comuniPerZona = risolviComuniPerZona(comuniZona, bollettino);

    const nuovoStato = { ...statoPrecedente };
    let emesse = 0;
    let saltate = 0;

    for (const [zonaNome, zonaInfo] of Object.entries(bollettino.zone || {})) {
        const comuni = comuniPerZona[zonaNome] || [];
        if (comuni.length === 0) {
            console.warn(`Zona ${zonaNome} non ha comuni mappati in comuni_zone.json, salto.`);
            continue;
        }
        const area = costruisciArea(zonaNome, comuni, geoIndice);
        const risultato = elaboraZona(zonaNome, zonaInfo, bollettino, statoPrecedente[zonaNome], awarenessTypes, area);

        if (risultato.azione === 'nessuna-allerta' || risultato.azione === 'invariato') {
            console.log(`Zona ${zonaNome}: ${risultato.azione === 'nessuna-allerta' ? 'nessuna allerta attiva' : 'stato CAP invariato'}, salto.`);
            saltate++;
            continue;
        }

        const { xml: xmlFirmato, firmato } = firmaXml(risultato.xml);
        console.log(`Zona ${zonaNome}: ${risultato.azione.toUpperCase()} - ${risultato.identifier}${firmato ? ' [firmato]' : ' [NON firmato]'}`);

        if (DRY_RUN) {
            console.log(`--- [DRY RUN] contenuto non scritto per ${risultato.identifier} ---`);
        } else {
            scriviAlertFile(CAP_OUTPUT_DIR, risultato.identifier, xmlFirmato);
        }
        nuovoStato[zonaNome] = risultato.nuovoStato;
        emesse++;
    }

    if (!DRY_RUN) {
        fs.mkdirSync(CAP_OUTPUT_DIR, { recursive: true });
        pubblicaChiavePubblica(CAP_OUTPUT_DIR);
        fs.writeFileSync(path.join(CAP_OUTPUT_DIR, 'index.atom'), costruisciAtom(nuovoStato));
        scriviStato(CAP_STATE_PATH, nuovoStato);
    }

    console.log(`${emesse} messaggi CAP emessi, ${saltate} zone saltate (nessuna allerta o stato invariato).`
        + `${DRY_RUN ? ' [DRY RUN: nessun file scritto, stato non salvato]' : ''}`);
}

main().catch((e) => {
    console.error('Errore nella generazione del feed CAP:', e);
    process.exit(1);
});
