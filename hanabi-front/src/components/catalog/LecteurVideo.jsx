/** Lecteur vidéo de la boutique : lecture, position, son, plein écran, clavier.
 *  Chargé à part, seulement sur une fiche qui a une vidéo. */
import { useEffect, useRef, useState } from "react";
import { Maximize, Pause, Play, Volume2, VolumeX } from "lucide-react";
import { useT } from "../../i18n/context.jsx";

const minutes = (s) => {
  const t = Math.max(0, Math.floor(s || 0));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
};

export default function LecteurVideo({ src, titre, autoLecture = false }) {
  const t = useT();
  const cadre = useRef(null);
  const video = useRef(null);
  const [lecture, setLecture] = useState(false);
  const [temps, setTemps] = useState(0);
  const [duree, setDuree] = useState(0);
  const [muet, setMuet] = useState(false);

  // Choisie d'un clic : elle part tout de suite, le clic vaut autorisation du son
  useEffect(() => {
    if (!autoLecture) return;
    const v = video.current;
    v?.play?.()?.catch(() => {
      // Refusée malgré tout (réglage du navigateur) : sans le son, elle passe
      if (!v) return;
      v.muted = true;
      setMuet(true);
      v.play().catch(() => {});
    });
  }, [autoLecture, src]);

  const basculer = () => {
    const v = video.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => {});
    else v.pause();
  };
  const deplacer = (secondes) => {
    const v = video.current;
    if (v) v.currentTime = Math.min(Math.max(0, secondes), v.duration || secondes);
  };
  const couper = () => {
    const v = video.current;
    if (!v) return;
    v.muted = !v.muted;
    setMuet(v.muted);
  };
  const pleinEcran = () => {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else cadre.current?.requestFullscreen?.();
  };

  const clavier = (e) => {
    if (e.target.type === "range") return;
    const action = {
      " ": basculer,
      k: basculer,
      m: couper,
      f: pleinEcran,
      ArrowRight: () => deplacer(temps + 5),
      ArrowLeft: () => deplacer(temps - 5),
    }[e.key];
    if (!action) return;
    e.preventDefault();
    action();
  };

  return (
    <div
      ref={cadre}
      className="lecteur"
      data-lecture={lecture || undefined}
      role="group"
      aria-label={titre}
      tabIndex={0}
      onKeyDown={clavier}
    >
      <video
        ref={video}
        src={src}
        playsInline
        preload="metadata"
        onClick={basculer}
        onPlay={() => setLecture(true)}
        onPause={() => setLecture(false)}
        onEnded={() => setLecture(false)}
        onTimeUpdate={(e) => setTemps(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => setDuree(e.currentTarget.duration)}
      />
      {!lecture && (
        <button
          type="button"
          className="lecteur-grand"
          onClick={basculer}
          aria-label={t("videoPlay")}
        >
          <Play size={30} aria-hidden="true" />
        </button>
      )}
      <div className="lecteur-barre">
        <button
          type="button"
          onClick={basculer}
          aria-label={lecture ? t("videoPause") : t("videoPlay")}
        >
          {lecture ? <Pause size={18} aria-hidden="true" /> : <Play size={18} aria-hidden="true" />}
        </button>
        <input
          type="range"
          min={0}
          max={duree || 0}
          step={0.1}
          value={temps}
          onChange={(e) => deplacer(Number(e.target.value))}
          aria-label={t("videoPosition")}
          aria-valuetext={`${minutes(temps)} / ${minutes(duree)}`}
        />
        <span className="lecteur-temps" aria-hidden="true">
          {minutes(temps)} / {minutes(duree)}
        </span>
        <button
          type="button"
          onClick={couper}
          aria-label={muet ? t("videoUnmute") : t("videoMute")}
          aria-pressed={muet}
        >
          {muet ? (
            <VolumeX size={18} aria-hidden="true" />
          ) : (
            <Volume2 size={18} aria-hidden="true" />
          )}
        </button>
        <button type="button" onClick={pleinEcran} aria-label={t("videoFullscreen")}>
          <Maximize size={18} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
