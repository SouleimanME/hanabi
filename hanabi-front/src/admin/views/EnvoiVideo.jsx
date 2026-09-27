/** Envoi d'une vidéo vers R2 : l'API délivre une autorisation signée, le
 *  navigateur dépose le fichier directement, sans passer par l'API. Absent si
 *  R2 n'est pas configuré. Chargé à part, à l'ouverture d'une fiche. */
import { useEffect, useState } from "react";
import { Film } from "lucide-react";

import { api } from "../api.js";

function deposer(envoi, entetes, fichier, onProgression) {
  return new Promise((resolve, reject) => {
    // XMLHttpRequest plutôt que fetch : lui seul donne la progression d'un envoi
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", envoi);
    Object.entries(entetes).forEach(([k, v]) => xhr.setRequestHeader(k, v));
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgression(e.loaded / e.total);
    xhr.onload = () =>
      xhr.status >= 200 && xhr.status < 300
        ? resolve()
        : reject(new Error(`Dépôt refusé par le stockage (${xhr.status}).`));
    xhr.onerror = () =>
      reject(new Error("Dépôt impossible : vérifier la règle CORS du seau R2 (voir DEPLOY.md)."));
    xhr.send(fichier);
  });
}

export default function EnvoiVideo({ onAjout }) {
  const [etat, setEtat] = useState(null);
  const [progression, setProgression] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    let actif = true;
    api("/admin/medias/etat")
      .then((e) => actif && setEtat(e))
      .catch(() => actif && setEtat(null));
    return () => {
      actif = false;
    };
  }, []);

  if (!etat?.videos) return null;

  const choisir = async (e) => {
    const fichier = e.target.files?.[0];
    e.target.value = "";
    if (!fichier) return;
    setErreur(null);
    if (!etat.types.includes(fichier.type)) {
      setErreur("Vidéo attendue en MP4, WebM ou MOV.");
      return;
    }
    if (fichier.size > etat.taille_max) {
      setErreur(`Vidéo de ${Math.round(etat.taille_max / 1048576)} Mo au plus.`);
      return;
    }
    setProgression(0);
    try {
      const autorisation = await api("/admin/medias/video", {
        method: "POST",
        body: { type: fichier.type, taille: fichier.size },
      });
      await deposer(autorisation.envoi, autorisation.entetes, fichier, setProgression);
      onAjout(autorisation.url);
    } catch (err) {
      setErreur(err.message);
    } finally {
      setProgression(null);
    }
  };

  return (
    <>
      <label className="img-upload-zone">
        <input
          type="file"
          accept={etat.types.join(",")}
          onChange={choisir}
          className="sr-only"
          disabled={progression !== null}
        />
        <span className="img-upload-inner">
          <Film size={20} aria-hidden="true" />
          <span>
            {progression === null
              ? "Ajouter une vidéo"
              : `Envoi de la vidéo : ${Math.round(progression * 100)} %`}
            <small>MP4, WebM ou MOV, {Math.round(etat.taille_max / 1048576)} Mo au plus</small>
          </span>
        </span>
      </label>
      {progression !== null && (
        <progress className="video-progression" value={progression} max={1}>
          {Math.round(progression * 100)} %
        </progress>
      )}
      {erreur && (
        <div className="adm-err" role="alert">
          {erreur}
        </div>
      )}
    </>
  );
}
