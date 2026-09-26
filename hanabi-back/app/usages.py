"""Usages des objets du catalogue de départ : ce qu'est l'objet, où il se pose,
pour qui, à quelle occasion. Invisibles sur la fiche, ils nourrissent la
recherche : « veilleuse » ou « démon » ne figurent dans aucune accroche.

Une ligne par usage. Le marchand les modifie dans le back-office.
"""

USAGES: dict[str, str] = {
    "HNB-052": "\n".join([
        "Kitsune, l'esprit renard du folklore japonais, un yokai messager d'Inari",
        "Figurine à poser sur une étagère, un bureau ou une bibliothèque",
        "Cadeau pour un amateur de mythologie japonaise, de yokai ou d'animés",
    ]),
    "HNB-018": "\n".join([
        "Le chat qui salue de la patte, porte-bonheur japonais qui attire la chance et la prospérité",
        "Se pose à l'entrée d'une boutique, d'un restaurant ou près d'une caisse",
        "Fonctionne à la lumière, sans pile",
        "Cadeau pour une inauguration, un nouveau travail ou un nouveau logement",
    ]),
    "HNB-067": "\n".join([
        "Poupée de vœux japonaise : on peint un œil en formulant un souhait, le second quand il se réalise",
        "Symbole de persévérance et de réussite, pour un examen, un projet ou la nouvelle année",
        "Porte-bonheur à poser sur un bureau",
    ]),
    "HNB-071": "\n".join([
        "Poupée japonaise traditionnelle en bois, originaire du nord du Japon",
        "Décoration pour une étagère, une commode ou une chambre",
        "Cadeau de naissance ou d'amitié, artisanat tourné et peint à la main",
    ]),
    "HNB-074": "\n".join([
        "Dragon japonais, gardien de l'eau, symbole de force et de sagesse",
        "Figurine de collection pour un bureau ou une vitrine",
        "Cadeau pour un amateur de dragons, de mythologie ou de fantasy",
    ]),
    "HNB-037": "\n".join([
        "Éventail pliant japonais, à ouvrir en été ou à exposer ouvert au mur",
        "Décoration murale légère, pour un salon ou un bureau",
        "Accessoire de cérémonie, de danse ou de costume",
    ]),
    "HNB-061": "\n".join([
        "Masque de renard des fêtes et des matsuri japonais, lié aux esprits yokai",
        "Décoration murale à accrocher, ou masque à porter pour un costume ou un cosplay",
        "Cadeau pour un fan d'animés, de yokai ou de culture japonaise",
    ]),
    "HNB-064": "\n".join([
        "Masque de démon du théâtre nô, une femme changée en démon par la jalousie",
        "Décoration murale forte pour un salon, un bureau ou un dojo",
        "Pour les amateurs de théâtre japonais, de tatouage traditionnel ou d'arts martiaux",
    ]),
    "HNB-078": "\n".join([
        "Reproduction de l'estampe ukiyo-e de Hokusai, la grande vague au large de Kanagawa",
        "Tableau à encadrer, art mural pour un salon, une chambre ou un bureau",
        "Cadeau pour un amateur d'art japonais, de la mer ou du surf",
    ]),
    "HNB-021": "\n".join([
        "Veilleuse en forme de torii, le portail des sanctuaires shinto",
        "Lumière douce pour une chambre, une table de chevet ou un bureau",
        "Alimentée par USB, trois niveaux de lumière",
    ]),
    "HNB-026": "\n".join([
        "Lampe en forme de pleine lune, lumière douce et colorée",
        "Veilleuse pour une chambre d'enfant ou une table de chevet, ambiance de salon",
        "Cadeau pour un enfant, un adolescent ou un amateur d'astronomie",
    ]),
    "HNB-083": "\n".join([
        "Lanterne chōchin comme celles des échoppes de ramen et des izakaya",
        "Éclairage d'ambiance chaleureux pour un salon, une cuisine, un bar ou un balcon",
        "Décoration pour une soirée japonaise ou un restaurant",
    ]),
}
