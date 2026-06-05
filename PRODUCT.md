# Product

## Register

product

## Users

Germain — utilisateur unique et propriétaire. Contexte : un « life OS » personnel,
local-first, lancé sur sa propre machine (localhost) et utilisé quotidiennement à
travers de nombreux domaines de vie. Deux modes d'usage : des check-ins rapides
(logger une série d'entraînement, cocher une habitude, jeter un œil au portefeuille)
et des sessions plus profondes (analyse Buffett, stats d'études, planification des
repas). Utilisateur expert de son propre outil — pas d'onboarding pour inconnus.

## Product Purpose

Mission Control unifie la gestion personnelle de Germain sur ~16 modules : finance
(investissement long terme façon Buffett), santé/nutrition, garde-robe, cuisine,
agenda, études, entraînement, budget, habitudes, livres, films/musique/séries, et un
module Robot/IA. Il remplace des tableurs et applis éparpillés par une seule surface
cohérente adossée à une base SQLite locale et privée. La réussite : un usage
quotidien fiable et rapide où l'outil s'efface derrière la tâche, et où la donnée
reste toujours lisible et à jour.

## Brand Personality

Posé, éditorial, durable. Une confiance tranquille — « Paper & Ink », retenue
« Old Money ». Calme et intemporel plutôt que tendance : l'interface se lit comme
un document bien composé, pas comme un dashboard à la mode. Voix : précise, sobre,
en français (fr-CA), sans jargon marketing.

## Anti-references

- Les dashboards « AI SaaS » génériques : dégradés crème-et-violet, grilles de
  cartes identiques, gabarit hero-metric, eyebrows en petites majuscules trackées
  au-dessus de chaque section.
- Les kits Material/Bootstrap par défaut : composants non travaillés, ombres
  lourdes, look « admin panel » générique.
- (À éviter aussi : fintech navy-and-gold clinquant / glassmorphism, gamification
  envahissante.)

## Design Principles

1. **L'outil s'efface derrière la tâche.** Familiarité gagnée, affordances
   standard, aucun contrôle réinventé pour le style.
2. **L'identité, c'est le système éditorial.** Honorer les tokens Heritage déjà
   commités (crème/marine, Libre Caslon + Public Sans, palette restreinte) ;
   l'étendre, ne pas le réinventer écran par écran.
3. **Lisibilité de la donnée d'abord.** Chiffres tabulaires, hiérarchie nette,
   contraste confortable même sans cible WCAG formelle.
4. **Cohérence plutôt que surprise.** Un seul vocabulaire de boutons, de contrôles
   de formulaire et d'icônes sur tous les modules ; le délice est réservé aux
   moments, pas étalé sur les pages.
5. **Retenue intentionnelle.** La couleur porte l'état et l'action primaire, pas la
   décoration ; le mouvement traduit un état (150–250 ms), jamais une chorégraphie.

## Accessibility & Inclusion

Outil personnel mono-utilisateur, sans cible WCAG officielle. Malgré tout : garder
un corps de texte lisible (viser ~AA, déjà recherché dans les tokens), un focus
clavier visible, et des alternatives `prefers-reduced-motion`. Ne pas coder une
information par la couleur seule quand un label ou une icône suffit.
