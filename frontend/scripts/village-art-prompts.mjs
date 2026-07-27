/**
 * Écrit les 33 fichiers de prompt du village.
 *
 * Le préambule de style est repris MOT POUR MOT dans chaque prompt : c'est lui,
 * et rien d'autre, qui fait tenir le monde ensemble (même angle, même matière,
 * même lumière, même palette). Seule la ligne « Subject » change.
 */

import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const OUT = process.argv[2];
mkdirSync(OUT, { recursive: true });

const PREAMBLE =
  "Soft matte low-poly clay diorama, isometric 3/4 view from above, tilt-shift miniature model, " +
  "warm diffuse afternoon light with a soft contact shadow, gentle ambient occlusion, no harsh speculars. " +
  "Muted editorial palette, strictly limited to: cream #faf9f5, midnight navy #04142c, brass #C5A059, " +
  "english green #536252, oxblood #501312, slate blue #384762. " +
  "A single small floating island of matte clay, centred in frame with generous empty margin around it, " +
  "resting on a plain solid pure white #ffffff background. " +
  "Every structure is a closed solid volume: no open archways, no gaps and no windows that let the white " +
  "background show through the model. " +
  "No text, no letters, no numbers, no logos, no signage, no people, no faces. Wide 3:2 landscape.";

/** Les 7 quartiers : un îlot, plusieurs petits bâtiments, des sentiers. */
const DISTRICTS = {
  execution:
    "a miniature control quarter of a tiny clay village — a slender clock tower with a plain blank dial, " +
    "a small domed observatory, and a low command pavilion, arranged around a round paved plaza with a " +
    "clay sundial at its centre, linked by stepping-stone paths.",
  finances:
    "a miniature banking quarter of a tiny clay village — a small columned exchange house, a squat vault " +
    "building with a round brass door, a narrow counting house, and a low treasury shed, with stacks of " +
    "clay coins and a balance scale on the plaza between them.",
  corps:
    "a miniature wellness quarter of a tiny clay village — a small gym pavilion with a clay dumbbell rack " +
    "outside, a low closed kitchen house with crates of clay vegetables, a compact clinic, and a tiny " +
    "greenhouse, all clustered on one island with clay footpaths and two rounded shrubs.",
  carriere:
    "a miniature campus quarter of a tiny clay village — a small lecture hall with a colonnade, a corner " +
    "café workshop with a striped awning, and a slender lighthouse on a rocky spur, joined by stepped " +
    "clay paths and a stack of oversized clay books.",
  culture:
    "a miniature culture quarter of a tiny clay village — a shell-shaped concert pavilion, a small cinema " +
    "with a rounded blank marquee, a library with tall closed shelves, and a compact arcade hut, around a " +
    "little plaza with a clay gramophone horn sculpture.",
  style:
    "a miniature style and travel quarter of a tiny clay village — a tailor's atelier with clay mannequins " +
    "outside, a tiny harbour house with a small clay boat at a jetty, and a pavilion with a torii-like " +
    "gate, joined by paths around a compass rose inlaid in the ground.",
  configuration:
    "a miniature utility quarter of a tiny clay village — an archive building with rows of clay drawers, " +
    "a machine shed with large exposed clay gears, a stubby server hut with stacked clay drums, and a " +
    "small workshop with oversized dials on its wall, linked by narrow service paths.",
};

/** Les 26 bâtiments : UN seul bâtiment par îlot, plus quelques accessoires. */
const BUILDINGS = {
  agenda:
    "a single slender clay clock tower with a plain blank circular dial and a colonnade of seven arched " +
    "recesses at its base, on a small round island with a stepped path and one shrub.",
  score:
    "a single small clay observatory with a domed roof, a ring-shaped brass gauge sculpture standing on " +
    "the lawn in front of it, on a small round island with a short path.",
  documents:
    "a single low clay archive pavilion, its front wall made of rows of small closed drawers with brass " +
    "handles, a wax-seal disc sculpture beside the door, on a small round island.",
  jobs: "a single clay machine shed with large exposed brass gears turning on its flank and a short " +
    "conveyor ramp beside it, on a small round island with tool crates.",
  routines:
    "a single clay automaton house crowned with four rotating vanes like a windmill, a long pendulum " +
    "hanging in a glazed niche on its facade, on a small round island.",
  donnees:
    "a single squat clay vault house with a thick rounded door, flanked by stacks of cylindrical clay " +
    "drums like oversized spools, on a small round island.",
  parametres:
    "a single small clay workshop hut whose front wall carries oversized sliders and rotary dials with " +
    "blank faces, a brass lever beside the door, on a small round island.",
  budget:
    "a single small clay counting house with a brass balance scale standing outside and neat stacks of " +
    "clay coins beside it, on a small round island with a short path.",
  finance:
    "a single columned clay exchange building, with a stepped sculpture of rising rectangular blocks " +
    "standing on the lawn in front, on a small round island.",
  patrimoine:
    "a single heavy clay treasury with a low rounded vault door and stacks of brass ingots piled beside " +
    "it, on a small rocky island.",
  credit:
    "a single clay bridge-house spanning a narrow cleft in the island, a taut brass cable and a carved " +
    "milestone marker at one end, on a small rocky island.",
  entrainement:
    "a single clay training pavilion with a barbell rack and a weight bench outside, and a short oval " +
    "running track curving around it, on a small round island.",
  cuisine:
    "a single closed clay kitchen house with a chimney hearth, hanging brass pots on its outer wall and " +
    "crates of clay vegetables by the door, on a small round island.",
  sante:
    "a single small clay clinic pavilion with a rounded arch sculpture shaped like a heartbeat line on " +
    "the lawn, and low herb beds beside it, on a small round island.",
  skincare:
    "a single clay bathhouse hut with a round water basin outside and a shelf of small stoppered clay " +
    "bottles along its wall, steam curling from the basin, on a small round island.",
  etudes:
    "a single clay lecture hall with a short colonnade and a stack of oversized closed clay books on the " +
    "steps outside, on a small round island.",
  travail:
    "a single clay corner café house with a striped awning, a brass espresso machine on the outdoor " +
    "counter and two small stools, on a small round island.",
  objectifs:
    "a single tall clay lighthouse on a rocky spur, its lantern room closed and unlit, a long stepped " +
    "path climbing to its door, on a small rocky island.",
  musique:
    "a single shell-shaped clay concert pavilion with a large brass gramophone horn sculpture standing " +
    "beside it, on a small round island.",
  film: "a single small clay cinema with a rounded blank marquee canopy and a clay projector on a tripod " +
    "standing outside, on a small round island.",
  series:
    "a single clay broadcast house with a slender antenna mast on its roof and three stacked blank clay " +
    "screens leaning against its wall, on a small round island.",
  livres:
    "a single clay library building with tall closed bookshelves visible as relief on its facade and a " +
    "reading bench outside, on a small round island with one shrub.",
  gaming:
    "a single small clay arcade hut, its facade decorated with an oversized joystick and four round " +
    "buttons in brass and oxblood, on a small round island.",
  garderobe:
    "a single clay tailor's atelier with two headless clay mannequins and a rail of folded garments " +
    "outside, a tall standing mirror beside the door, on a small round island.",
  voyage:
    "a single small clay harbour house with a wooden jetty and a little clay sailing boat moored to it, " +
    "a signpost with blank arrow boards, on a small round island.",
  langues:
    "a single clay pavilion combining a torii-like gate with a short colonnade, racks of rolled clay " +
    "scrolls stacked beside the entrance, on a small round island.",
};

let n = 0;
for (const [slug, subject] of Object.entries(DISTRICTS)) {
  writeFileSync(join(OUT, `d_${slug}.txt`), `${PREAMBLE}\n\nSubject: ${subject}\n`, "utf8");
  n++;
}
for (const [slug, subject] of Object.entries(BUILDINGS)) {
  writeFileSync(join(OUT, `b_${slug}.txt`), `${PREAMBLE}\n\nSubject: ${subject}\n`, "utf8");
  n++;
}
console.log(`${n} prompts ecrits (${Object.keys(DISTRICTS).length} quartiers + ${Object.keys(BUILDINGS).length} batiments)`);
