/** Textes legaux affiches en modale : mentions, CGV, confidentialite, cookies.
 *
 * Perimetre couvert : les obligations minimales d'un site marchand francais
 * vendant a des consommateurs de l'Union europeenne.
 *   - Mentions legales : LCEN art. 6-III (editeur, hebergeur, contact).
 *   - CGV : Code de la consommation (information precontractuelle L221-5,
 *     retractation L221-18 a L221-28 + formulaire type annexe R221-1,
 *     garantie legale de conformite L217-3 et suivants, vices caches
 *     art. 1641 du Code civil, mediation L612-1).
 *   - Confidentialite : RGPD art. 13 (toutes les mentions obligatoires).
 *   - Cookies : art. 82 loi Informatique et Libertes et lignes directrices CNIL.
 *
 * IMPORTANT - deux limites a lever avant toute mise en ligne reelle :
 *   1. Les valeurs entre crochets [ ] sont des champs a completer. Aucune
 *      identite d'entreprise n'a ete inventee : un SIRET, un capital ou une
 *      adresse fictifs seraient une fausse mention legale.
 *   2. Ces textes sont une base de travail, pas un avis juridique. Une
 *      relecture par un professionnel est recommandee.
 *
 * Le francais fait foi : c'est la seule version complete, les traductions sont
 * fournies pour le confort de lecture (voir FALLBACK_LANG dans LegalModal).
 *
 * Format du corps : une ligne entouree de ** devient un titre, une ligne
 * commencant par une puce devient un element de liste (voir LegalModal).
 */

/** Derniere revision des textes, affichee en pied de chaque page legale. */
export const LEGAL_UPDATED = "30 juillet 2026";

export const LEGAL_CONTENT = {
  mentions: {
    fr: {
      title: "Mentions légales",
      body: `**Éditeur du site**
Hanabi - Objets japonais choisis
Forme juridique : [forme juridique - ex. SASU, SARL, entrepreneur individuel]
Capital social : [montant] €
Siège social : [adresse complète]
RCS : [ville] [numéro] - SIRET : [numéro à 14 chiffres]
N° TVA intracommunautaire : [FR + 11 caractères]
Téléphone : [numéro]
E-mail : contact@hanabi.fr

**Directeur de la publication**
[Prénom Nom], en qualité de [fonction]

**Hébergeur**
[Dénomination sociale de l'hébergeur]
[Adresse complète]
Téléphone : [numéro]

**Propriété intellectuelle**
L'ensemble des contenus de ce site (textes, visuels, motifs, code) est protégé par le droit d'auteur et demeure la propriété exclusive de Hanabi ou de ses ayants droit. Toute reproduction, représentation ou adaptation, totale ou partielle, sans autorisation écrite préalable est interdite et constitue une contrefaçon au sens des articles L335-2 et suivants du Code de la propriété intellectuelle.

**Responsabilité**
Hanabi s'efforce d'assurer l'exactitude des informations publiées. Une erreur ou une omission ne saurait toutefois engager sa responsabilité. Les liens vers des sites tiers ne sauraient engager la responsabilité de Hanabi quant à leur contenu.

**Signalement de contenu illicite**
Conformément à l'article 6-I-5 de la LCEN, tout contenu manifestement illicite peut être signalé à : contact@hanabi.fr

**Accessibilité**
Ce site est conçu pour rester utilisable au clavier, avec un lecteur d'écran, et respecte le réglage système de réduction des animations. Toute difficulté d'accès peut être signalée à : contact@hanabi.fr`,
    },
    en: {
      title: "Legal notice",
      body: `**Publisher**
Hanabi - Chosen Japanese objects
Legal form: [legal form]
Share capital: [amount] €
Registered office: [full address]
Trade register: [city] [number] - SIRET: [14-digit number]
VAT number: [FR + 11 characters]
Phone: [number]
E-mail: contact@hanabi.fr

**Publication director**
[First name Last name]

**Hosting provider**
[Host company name], [full address], phone: [number]

**Intellectual property**
All content on this site (text, images, patterns, code) is protected by copyright and remains the exclusive property of Hanabi. Any reproduction without prior written permission is prohibited.

**Liability**
Hanabi strives to keep the published information accurate but cannot be held liable for errors or omissions.

**Accessibility**
This site is built to remain usable with a keyboard and a screen reader, and honours the system reduced-motion setting. Report any access issue to contact@hanabi.fr

The French version of these notices is the legally authoritative one.`,
    },
    es: {
      title: "Aviso legal",
      body: `**Editor**
Hanabi - Objetos japoneses escogidos
Forma jurídica: [forma jurídica]
Capital social: [importe] €
Domicilio social: [dirección completa]
Registro mercantil: [ciudad] [número] - SIRET: [número de 14 cifras]
NIF-IVA: [FR + 11 caracteres]
Teléfono: [número]
Correo: contact@hanabi.fr

**Director de publicación**
[Nombre y apellidos]

**Alojamiento**
[Denominación del proveedor], [dirección completa], teléfono: [número]

**Propiedad intelectual**
Todo el contenido de este sitio está protegido por derechos de autor y es propiedad exclusiva de Hanabi. Queda prohibida su reproducción sin autorización escrita previa.

**Accesibilidad**
Este sitio está diseñado para poder usarse con teclado y lector de pantalla, y respeta la preferencia del sistema de reducción de animaciones.

La versión francesa de estos avisos es la jurídicamente vinculante.`,
    },
  },
  cgv: {
    fr: {
      title: "Conditions Générales de Vente",
      body: `**Article 1 - Objet et champ d'application**
Les présentes conditions générales de vente régissent sans restriction ni réserve l'ensemble des ventes conclues à distance entre Hanabi (ci-après « le Vendeur ») et tout consommateur (ci-après « l'Acheteur ») via le site hanabi.fr. Elles sont communiquées à l'Acheteur avant la passation de commande et leur acceptation est obligatoire pour commander.

**Article 2 - Produits et caractéristiques essentielles**
Les caractéristiques essentielles de chaque produit (matière, dimensions, contenance, entretien) figurent sur sa fiche. Les photographies et motifs illustrant les produits n'entrent pas dans le champ contractuel et ne peuvent engager le Vendeur. Les offres sont valables dans la limite des stocks disponibles.

**Article 3 - Prix**
Les prix sont indiqués en euros toutes taxes comprises (TVA française applicable au jour de la commande), hors frais de livraison. Les frais de livraison sont indiqués avant la validation de la commande et rappelés dans le récapitulatif. Le Vendeur se réserve le droit de modifier ses prix à tout moment ; les produits sont facturés au tarif en vigueur au moment de l'enregistrement de la commande.

**Article 4 - Commande**
L'Acheteur sélectionne ses produits, vérifie le récapitulatif (contenu, prix total, frais de livraison, adresse) et valide sa commande. La validation vaut acceptation des prix et des présentes CGV. La commande n'est définitive qu'après confirmation du paiement. Un accusé de réception récapitulant la commande est adressé par courrier électronique.

**Article 5 - Paiement**
Le paiement est exigible immédiatement à la commande. Moyens acceptés : [liste des moyens de paiement acceptés]. Les paiements sont traités par [prestataire de paiement], via une connexion chiffrée ; le Vendeur n'a jamais accès aux données bancaires complètes de l'Acheteur.

**Article 6 - Livraison**
Les produits sont livrés à l'adresse indiquée par l'Acheteur. Les commandes sont préparées sous 48 heures ouvrées. Les frais de livraison sont offerts à partir de 80 € d'achat.
Conformément à l'article L216-1 du Code de la consommation, la livraison intervient au plus tard trente (30) jours après la conclusion du contrat. À défaut, l'Acheteur peut mettre le Vendeur en demeure de livrer dans un délai supplémentaire raisonnable, puis résoudre le contrat si la livraison n'intervient pas. Les sommes versées lui sont alors remboursées au plus tard dans les quatorze (14) jours suivant la résolution.
Le risque de perte ou d'endommagement est transféré à l'Acheteur au moment où il prend physiquement possession du produit.

**Article 7 - Droit de rétractation**
Conformément aux articles L221-18 et suivants du Code de la consommation, l'Acheteur dispose d'un délai de quatorze (14) jours à compter de la réception du produit pour exercer son droit de rétractation, sans avoir à motiver sa décision ni à supporter de pénalité.
Pour exercer ce droit, l'Acheteur notifie sa décision par toute déclaration dénuée d'ambiguïté, par courrier électronique à contact@hanabi.fr ou en utilisant le formulaire type reproduit à l'article 8.
Les produits doivent être retournés dans un état permettant leur remise en vente, au plus tard quatorze (14) jours après la notification. Les frais directs de retour sont à la charge de l'Acheteur, sauf produit défectueux ou non conforme.
Le remboursement intervient au plus tard quatorze (14) jours à compter de la récupération des produits ou de la preuve de leur expédition, par le même moyen de paiement que celui utilisé pour la commande.
Exceptions légales (article L221-28) : ne peuvent être retournés les biens confectionnés selon les spécifications du consommateur ou nettement personnalisés, ni les biens descellés ne pouvant être renvoyés pour des raisons d'hygiène ou de protection de la santé.

**Article 8 - Formulaire type de rétractation**
(À compléter et renvoyer uniquement en cas de rétractation.)
À l'attention de Hanabi, [adresse complète], contact@hanabi.fr :
Je vous notifie par la présente ma rétractation du contrat portant sur la vente du bien ci-dessous :
• Commandé le [date] / reçu le [date]
• Référence(s) et désignation du ou des produits
• Nom du consommateur
• Adresse du consommateur
• Signature (uniquement en cas de notification sur papier)
• Date

**Article 9 - Garantie légale de conformité**
Le Vendeur est tenu des défauts de conformité du bien dans les conditions des articles L217-3 et suivants du Code de la consommation.
L'Acheteur dispose d'un délai de deux (2) ans à compter de la délivrance du bien pour agir. Il peut choisir entre la réparation et le remplacement, sous réserve des conditions de coût prévues à l'article L217-12. Il est dispensé de rapporter la preuve de l'existence du défaut de conformité pendant les vingt-quatre (24) mois suivant la délivrance.
Toute réparation au titre de la garantie légale de conformité prolonge celle-ci de six (6) mois. Lorsque l'Acheteur demande une réparation mais que le remplacement est effectué, une nouvelle garantie légale court à compter de la délivrance du bien de remplacement.
Cette garantie légale s'applique indépendamment de toute garantie commerciale éventuellement consentie.

**Article 10 - Garantie des vices cachés**
Indépendamment de la garantie précédente, l'Acheteur peut agir sur le fondement de la garantie des vices cachés des articles 1641 et suivants du Code civil, dans un délai de deux (2) ans à compter de la découverte du vice. Il peut alors choisir entre la résolution de la vente et une réduction du prix.

**Article 11 - Service après-vente et réclamations**
Toute réclamation peut être adressée à contact@hanabi.fr ou par téléphone au [numéro]. Le Vendeur s'engage à répondre dans un délai de [nombre] jours ouvrés.

**Article 12 - Médiation de la consommation**
Conformément à l'article L612-1 du Code de la consommation, l'Acheteur a le droit de recourir gratuitement à un médiateur de la consommation en vue de la résolution amiable d'un litige, après avoir tenté au préalable de le résoudre directement auprès du Vendeur par une réclamation écrite.
Médiateur compétent : [nom du médiateur agréé] - [adresse postale] - [site internet].
La saisine du médiateur doit intervenir dans un délai d'un an à compter de la réclamation écrite adressée au Vendeur.

**Article 13 - Données personnelles**
Les données collectées sont nécessaires au traitement de la commande. Leur traitement est décrit dans la Politique de confidentialité, accessible depuis le pied de page.

**Article 14 - Force majeure**
Aucune des parties ne pourra être tenue responsable d'un manquement dû à un événement de force majeure au sens de l'article 1218 du Code civil.

**Article 15 - Droit applicable et litiges**
Les présentes CGV sont soumises au droit français. En cas de litige, les tribunaux français sont compétents. Conformément à la réglementation européenne, le consommateur résidant dans un autre État membre conserve le bénéfice des dispositions impératives protectrices de la loi de son pays de résidence.`,
    },
    en: {
      title: "Terms and Conditions",
      body: `**Article 1 - Scope**
These terms govern all distance sales concluded between Hanabi (the "Seller") and any consumer (the "Buyer") via hanabi.fr. Acceptance is required in order to place an order.

**Article 2 - Prices**
Prices are stated in euros including VAT, excluding delivery costs. Delivery costs are shown before the order is confirmed.

**Article 3 - Payment and order**
Payment is due immediately upon ordering. The order becomes final once payment is confirmed. A confirmation e-mail is sent to the Buyer.

**Article 4 - Delivery**
Orders are prepared within 48 working hours. Delivery is free from €80. In accordance with French law, delivery takes place no later than thirty (30) days after the contract is concluded. Risk of loss passes to the Buyer upon physical possession.

**Article 5 - Right of withdrawal**
The Buyer has fourteen (14) days from receipt to withdraw, without giving reasons and without penalty, by any unambiguous statement sent to contact@hanabi.fr. Goods must be returned within fourteen (14) days of that notice, in resaleable condition. Direct return costs are borne by the Buyer unless the item is faulty or non-conforming. Refunds are issued within fourteen (14) days of recovering the goods or receiving proof of dispatch, using the original payment method.

**Article 6 - Legal guarantee of conformity**
The Seller is liable for lack of conformity for two (2) years from delivery. The Buyer may choose between repair and replacement, and need not prove the defect during the twenty-four (24) months following delivery. Any repair under this guarantee extends it by six (6) months.

**Article 7 - Hidden defects**
Independently, the Buyer may rely on the guarantee against hidden defects for two (2) years from discovery of the defect.

**Article 8 - Complaints and mediation**
Complaints: contact@hanabi.fr. After a written complaint to the Seller, the Buyer may refer the dispute free of charge to a consumer mediator: [approved mediator name, address, website].

**Article 9 - Governing law**
French law applies. Consumers resident in another EU Member State retain the benefit of the mandatory protective provisions of their country of residence.

The French version of these terms is the legally authoritative one.`,
    },
    es: {
      title: "Condiciones Generales de Venta",
      body: `**Artículo 1 - Objeto**
Las presentes condiciones rigen todas las ventas a distancia celebradas entre Hanabi (el «Vendedor») y cualquier consumidor (el «Comprador») a través de hanabi.fr.

**Artículo 2 - Precios**
Los precios se indican en euros con impuestos incluidos, sin gastos de envío. Los gastos de envío se muestran antes de confirmar el pedido.

**Artículo 3 - Pago y pedido**
El pago es exigible en el momento del pedido. El pedido es firme una vez confirmado el pago, con envío de un correo de confirmación.

**Artículo 4 - Entrega**
Los pedidos se preparan en 48 horas laborables. Envío gratuito a partir de 80 €. La entrega se realiza como máximo treinta (30) días después de la celebración del contrato. El riesgo se transmite al Comprador al tomar posesión física del producto.

**Artículo 5 - Derecho de desistimiento**
El Comprador dispone de catorce (14) días desde la recepción para desistir, sin motivación ni penalización, mediante declaración inequívoca a contact@hanabi.fr. Los productos deben devolverse en un plazo de catorce (14) días, en estado revendible. Los gastos directos de devolución corren a cargo del Comprador, salvo producto defectuoso o no conforme. El reembolso se efectúa en un plazo de catorce (14) días.

**Artículo 6 - Garantía legal de conformidad**
El Vendedor responde de la falta de conformidad durante dos (2) años desde la entrega. El Comprador puede elegir entre reparación y sustitución, y está exento de probar el defecto durante los veinticuatro (24) meses siguientes a la entrega.

**Artículo 7 - Vicios ocultos**
De forma independiente, el Comprador puede invocar la garantía por vicios ocultos durante dos (2) años desde el descubrimiento del vicio.

**Artículo 8 - Reclamaciones y mediación**
Reclamaciones: contact@hanabi.fr. Tras una reclamación escrita, el Comprador puede recurrir gratuitamente a un mediador de consumo: [nombre, dirección y web del mediador acreditado].

**Artículo 9 - Derecho aplicable**
Se aplica el derecho francés. Los consumidores residentes en otro Estado miembro conservan el beneficio de las disposiciones imperativas protectoras de su país de residencia.

La versión francesa de estas condiciones es la jurídicamente vinculante.`,
    },
  },
  confidentialite: {
    fr: {
      title: "Politique de confidentialité",
      body: `**Responsable du traitement**
Hanabi, [forme juridique], [adresse complète], représentée par [Prénom Nom].
Contact : contact@hanabi.fr
Délégué à la protection des données : [nom et contact du DPO, ou « aucun DPO désigné »]

**Données collectées et caractère obligatoire**
• Création de compte : civilité, nom, prénom, adresse électronique, date de naissance, mot de passe (conservé sous forme chiffrée et non réversible). Ces données sont nécessaires : sans elles, le compte ne peut être créé.
• Commande : adresse de livraison, contenu et montant de la commande, coordonnées de contact. Données nécessaires à l'exécution du contrat.
• Avis produit : note, texte, prénom affiché. Dépôt facultatif.
• Alerte de réapprovisionnement : adresse électronique. Dépôt facultatif.
• Données techniques : adresse IP et journaux de connexion du serveur, à des fins de sécurité.

**Finalités et bases légales**
• Gestion des commandes, de la livraison et du service après-vente - exécution du contrat (art. 6.1.b RGPD).
• Gestion du compte client et de l'authentification - exécution du contrat.
• Publication des avis produit - consentement (art. 6.1.a), retirable à tout moment.
• Alertes de réapprovisionnement - consentement.
• Prospection commerciale par courrier électronique, le cas échéant - consentement.
• Sécurité du service, prévention de la fraude et des abus - intérêt légitime (art. 6.1.f).
• Respect des obligations comptables et fiscales - obligation légale (art. 6.1.c).

**Destinataires**
Les données sont accessibles au personnel habilité de Hanabi et à ses sous-traitants, agissant sur instruction et liés par une obligation de confidentialité : hébergeur, prestataire de paiement, transporteur, service d'envoi de courriers électroniques. Aucune donnée n'est vendue, louée ou cédée à des tiers à des fins publicitaires.

**Transferts hors Union européenne**
Les données sont hébergées au sein de l'Union européenne. Si un sous-traitant conduisait un transfert vers un pays tiers, celui-ci serait encadré par une décision d'adéquation de la Commission européenne ou par les clauses contractuelles types, assorties des mesures complémentaires nécessaires.

**Durées de conservation**
• Compte client : durée de vie du compte, puis trois (3) ans à compter du dernier contact, avant suppression ou anonymisation.
• Commandes et pièces comptables : dix (10) ans, en application des obligations comptables (art. L123-22 du Code de commerce).
• Avis produit : jusqu'au retrait du consentement ou à la suppression du compte.
• Prospection : trois (3) ans à compter du dernier contact.
• Journaux de connexion : douze (12) mois.

**Vos droits**
Conformément aux articles 15 à 22 du RGPD, vous disposez d'un droit d'accès, de rectification, d'effacement, de limitation du traitement, d'opposition, de portabilité de vos données, ainsi que du droit de retirer votre consentement à tout moment lorsque le traitement repose sur celui-ci. Vous disposez également du droit de définir des directives sur le sort de vos données après votre décès.
Ces droits s'exercent à contact@hanabi.fr. Une réponse vous sera apportée dans un délai d'un (1) mois, prorogeable de deux (2) mois en cas de demande complexe. Une preuve d'identité peut être demandée en cas de doute raisonnable.

**Réclamation**
Vous pouvez introduire une réclamation auprès de la CNIL : 3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07 - www.cnil.fr

**Absence de décision automatisée**
Aucune décision produisant des effets juridiques à votre égard n'est prise sur le seul fondement d'un traitement automatisé. Aucun profilage n'est réalisé.

**Sécurité**
Les échanges avec le site sont chiffrés en transit. Les mots de passe sont stockés sous forme de condensats non réversibles. Les accès aux données sont limités aux personnes habilitées.`,
    },
    en: {
      title: "Privacy Policy",
      body: `**Data controller**
Hanabi, [legal form], [full address]. Contact: contact@hanabi.fr
Data protection officer: [name and contact, or "none appointed"]

**Data collected**
• Account: title, name, e-mail, date of birth, password (stored as a non-reversible hash) - required to create an account.
• Orders: delivery address, order contents and amount - required to perform the contract.
• Product reviews and restock alerts: optional.
• Technical data: IP address and server logs, for security purposes.

**Purposes and legal bases**
Order and after-sales management, account management - performance of the contract. Reviews, restock alerts and marketing e-mails - consent, withdrawable at any time. Service security and fraud prevention - legitimate interest. Accounting obligations - legal obligation.

**Recipients**
Authorised Hanabi staff and processors bound by confidentiality: hosting provider, payment provider, carrier, e-mail service. Data is never sold or rented to third parties.

**Transfers outside the EU**
Data is hosted within the European Union. Any transfer to a third country would be covered by an adequacy decision or the standard contractual clauses.

**Retention**
Account: life of the account, then three (3) years after last contact. Orders and accounting records: ten (10) years. Marketing: three (3) years after last contact. Server logs: twelve (12) months.

**Your rights**
Under Articles 15 to 22 GDPR you have the rights of access, rectification, erasure, restriction of processing, objection and portability, and the right to withdraw consent at any time. Exercise them at contact@hanabi.fr; you will receive a reply within one (1) month.

**Complaints**
You may lodge a complaint with the French supervisory authority, the CNIL: 3 place de Fontenoy, TSA 80715, 75334 Paris Cedex 07 - www.cnil.fr

**No automated decision-making**
No decision producing legal effects is taken solely on the basis of automated processing. No profiling is carried out.

The French version of this policy is the legally authoritative one.`,
    },
    es: {
      title: "Política de privacidad",
      body: `**Responsable del tratamiento**
Hanabi, [forma jurídica], [dirección completa]. Contacto: contact@hanabi.fr
Delegado de protección de datos: [nombre y contacto, o «no designado»]

**Datos recopilados**
• Cuenta: tratamiento, nombre, apellidos, correo, fecha de nacimiento, contraseña (almacenada como resumen no reversible) - necesarios para crear la cuenta.
• Pedidos: dirección de envío, contenido e importe - necesarios para ejecutar el contrato.
• Opiniones y avisos de reposición: facultativos.
• Datos técnicos: dirección IP y registros del servidor, con fines de seguridad.

**Finalidades y bases jurídicas**
Gestión de pedidos, entrega y posventa, y gestión de la cuenta - ejecución del contrato. Opiniones, avisos de reposición y comunicaciones comerciales - consentimiento, revocable en cualquier momento. Seguridad y prevención del fraude - interés legítimo. Obligaciones contables - obligación legal.

**Destinatarios**
Personal autorizado de Hanabi y encargados sujetos a confidencialidad: proveedor de alojamiento, de pago, transportista y servicio de correo. Los datos nunca se venden ni alquilan a terceros.

**Transferencias fuera de la UE**
Los datos se alojan en la Unión Europea. Cualquier transferencia a un tercer país estaría amparada por una decisión de adecuación o por las cláusulas contractuales tipo.

**Plazos de conservación**
Cuenta: vigencia de la cuenta y tres (3) años desde el último contacto. Pedidos y documentos contables: diez (10) años. Prospección: tres (3) años. Registros de conexión: doce (12) meses.

**Sus derechos**
Conforme a los artículos 15 a 22 del RGPD, tiene derecho de acceso, rectificación, supresión, limitación, oposición y portabilidad, así como a retirar su consentimiento en cualquier momento. Ejerza estos derechos en contact@hanabi.fr.

**Reclamación**
Puede presentar una reclamación ante la autoridad francesa de control, la CNIL: 3 place de Fontenoy, TSA 80715, 75334 París Cedex 07 - www.cnil.fr

**Ausencia de decisiones automatizadas**
No se adopta ninguna decisión con efectos jurídicos basada únicamente en un tratamiento automatizado. No se realiza elaboración de perfiles.

La versión francesa de esta política es la jurídicamente vinculante.`,
    },
  },
  cookies: {
    fr: {
      title: "Cookies et stockage local",
      body: `**Ce que ce site dépose sur votre appareil**
Ce site n'utilise aucun cookie publicitaire, aucun cookie de mesure d'audience et aucun traceur tiers. Il ne dépose pas de cookie au sens strict : il utilise le stockage local du navigateur (localStorage), qui relève des mêmes règles que les cookies au titre de l'article 82 de la loi Informatique et Libertés.

**Informations conservées**
• Panier en cours - pour ne pas perdre votre sélection en changeant de page.
• Préférence de thème (clair ou sombre) et de langue - pour retrouver votre réglage.
• Liste de favoris et produits vus récemment - pour vous les proposer à nouveau.
• Jeton de session, si vous êtes connecté - pour maintenir votre authentification.

**Pourquoi aucune bannière de consentement n'est affichée**
Ces informations sont strictement nécessaires à la fourniture d'un service que vous avez expressément demandé (tenir un panier, rester connecté, mémoriser vos préférences d'affichage). À ce titre, elles sont exemptées du recueil du consentement, conformément à l'article 82 de la loi Informatique et Libertés et aux lignes directrices de la CNIL. Aucune n'est utilisée pour vous suivre, vous profiler ou vous cibler publicitairement.
Si une mesure d'audience ou un outil tiers était ajouté au site, une bannière de consentement préalable serait mise en place et cette page mise à jour.

**Durée de conservation**
Ces informations restent dans votre navigateur jusqu'à ce que vous les supprimiez. Elles ne sont pas transmises à des tiers. Le jeton de session est effacé à la déconnexion.

**Comment les supprimer**
Vous pouvez à tout moment vider le stockage local et les cookies depuis les réglages de confidentialité de votre navigateur, ou en navigation privée. La suppression du panier et des préférences est sans conséquence : le site refonctionnera avec ses réglages par défaut.`,
    },
    en: {
      title: "Cookies and local storage",
      body: `**What this site stores on your device**
This site uses no advertising cookies, no analytics cookies and no third-party trackers. It does not set cookies in the strict sense: it uses the browser's local storage, which falls under the same rules as cookies.

**Information kept**
• Current cart - so your selection survives page changes.
• Theme (light or dark) and language preference.
• Wishlist and recently viewed products.
• Session token, if you are signed in.

**Why no consent banner is shown**
This information is strictly necessary to provide a service you explicitly requested (keeping a cart, staying signed in, remembering display preferences), and is therefore exempt from consent. None of it is used to track, profile or advertise to you. Should analytics or any third-party tool be added, a prior consent banner would be introduced and this page updated.

**Retention and deletion**
The information stays in your browser until you delete it, and is never shared with third parties. You can clear local storage and cookies at any time from your browser's privacy settings; the site will simply return to its default settings.

The French version of this page is the legally authoritative one.`,
    },
    es: {
      title: "Cookies y almacenamiento local",
      body: `**Qué almacena este sitio en su dispositivo**
Este sitio no utiliza cookies publicitarias, ni cookies de medición de audiencia, ni rastreadores de terceros. No instala cookies en sentido estricto: utiliza el almacenamiento local del navegador, sujeto a las mismas normas que las cookies.

**Información conservada**
• Carrito actual - para no perder su selección al cambiar de página.
• Preferencia de tema (claro u oscuro) e idioma.
• Lista de favoritos y productos vistos recientemente.
• Token de sesión, si ha iniciado sesión.

**Por qué no se muestra ningún banner de consentimiento**
Esta información es estrictamente necesaria para prestar un servicio que usted ha solicitado expresamente (mantener un carrito, permanecer conectado, recordar sus preferencias de visualización), por lo que está exenta de consentimiento. Ninguna se emplea para rastrearle, elaborar perfiles ni dirigirle publicidad. Si se añadiera una herramienta de analítica o de terceros, se implantaría un banner de consentimiento previo y se actualizaría esta página.

**Conservación y eliminación**
La información permanece en su navegador hasta que usted la elimine y nunca se comparte con terceros. Puede borrar el almacenamiento local y las cookies en cualquier momento desde los ajustes de privacidad de su navegador.

La versión francesa de esta página es la jurídicamente vinculante.`,
    },
  },
};
