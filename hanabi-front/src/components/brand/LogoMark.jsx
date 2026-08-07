/** Embleme Hanabi : torii, pleine lune, katanas croises et sakura.
 *
 * Dessine en SVG inline plutot qu'en fichier image : le logo suit la couleur
 * du theme, reste net a toute taille et n'ajoute aucune requete reseau.
 */

export function LogoMark({ size = 34 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 680 680"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <defs>
        <clipPath id="lm_circ">
          <circle cx="340" cy="340" r="296" />
        </clipPath>
        <radialGradient id="lm_pg" cx="50%" cy="85%" r="75%">
          <stop offset="0%" stopColor="#FBE3EC" />
          <stop offset="55%" stopColor="#F6C6D8" />
          <stop offset="100%" stopColor="#EBA7C2" />
        </radialGradient>
        <g id="lm_petal">
          <path
            d="M0,2 C -7,0 -9,-7 -7,-12 C -5,-17 -2,-20 0,-22 C 2,-20 5,-17 7,-12 C 9,-7 7,0 0,2 Z"
            fill="url(#lm_pg)"
          />
          <path
            d="M0,-22 C -1.5,-19.5 -2.2,-18 -2,-16 L0,-17.5 L2,-16 C2.2,-18 1.5,-19.5 0,-22 Z"
            fill="#15120D"
            opacity="0.18"
          />
          <path d="M0,-2 L0,-18" stroke="#E08FB0" strokeWidth="0.7" opacity="0.55" />
        </g>
        <g id="lm_bloom">
          <use href="#lm_petal" transform="rotate(0)" />
          <use href="#lm_petal" transform="rotate(72)" />
          <use href="#lm_petal" transform="rotate(144)" />
          <use href="#lm_petal" transform="rotate(216)" />
          <use href="#lm_petal" transform="rotate(288)" />
          <circle r="3" fill="#F4C04E" />
          <g stroke="#D98BAE" strokeWidth="0.9" strokeLinecap="round">
            <line x1="0" y1="0" x2="0" y2="-7" />
            <line x1="0" y1="0" x2="5" y2="-4" />
            <line x1="0" y1="0" x2="6" y2="2" />
            <line x1="0" y1="0" x2="-5" y2="-4" />
            <line x1="0" y1="0" x2="-6" y2="2" />
            <line x1="0" y1="0" x2="3" y2="6" />
            <line x1="0" y1="0" x2="-3" y2="6" />
          </g>
        </g>
      </defs>
      <circle cx="340" cy="340" r="340" fill="#100E0B" />
      <circle cx="340" cy="340" r="296" fill="#15120D" />
      <g clipPath="url(#lm_circ)">
        <circle cx="340" cy="312" r="150" fill="#EDE7D6" />
        <circle cx="300" cy="280" r="18" fill="#E0D8C2" opacity="0.5" />
        <circle cx="388" cy="340" r="24" fill="#E0D8C2" opacity="0.4" />
        <circle cx="356" cy="268" r="11" fill="#E0D8C2" opacity="0.5" />
        <g>
          <rect x="268" y="250" width="27" height="210" fill="#C2362A" rx="2" />
          <rect x="385" y="250" width="27" height="210" fill="#C2362A" rx="2" />
          <rect x="287" y="250" width="8" height="210" fill="#A12A20" rx="2" />
          <rect x="404" y="250" width="8" height="210" fill="#A12A20" rx="2" />
          <path d="M 228 220 Q 340 192 452 220 L 452 236 Q 340 210 228 236 Z" fill="#C2362A" />
          <path d="M 228 236 Q 340 210 452 236 L 450 248 Q 340 224 230 248 Z" fill="#A12A20" />
          <rect x="256" y="258" width="168" height="18" fill="#C2362A" rx="2" />
          <rect x="256" y="270" width="168" height="6" fill="#A12A20" rx="2" />
          <rect x="334" y="240" width="12" height="20" fill="#C2362A" />
        </g>
        <g>
          <path
            d="M 150 506 L 330 372 L 340 385 L 160 519 C 153 524 144 521 142 513 C 141 510 144 508 150 506 Z"
            fill="#221E18"
          />
          <path d="M 322 378 L 340 365 L 348 376 L 330 389 Z" fill="#3a3329" />
          <path
            d="M 142 513 C 141 510 144 508 150 506 L 158 512 C 152 514 149 518 151 522 C 146 522 143 518 142 513 Z"
            fill="#3a3329"
          />
          <path d="M 330 372 L 506 178 L 514 187 L 340 385 Z" fill="#1a1a1a" />
          <path d="M 332 374 L 505 182 L 509 186 L 336 379 Z" fill="#dcdcdc" />
          <path
            d="M 338 383 L 512 190"
            stroke="#ffffff"
            strokeWidth="1.4"
            opacity="0.85"
            fill="none"
            strokeLinecap="round"
          />
          <path d="M 506 178 L 524 158 L 520 182 L 514 187 Z" fill="#1a1a1a" />
          <path d="M 507 180 L 523 160 L 519 180 Z" fill="#e6e6e6" />
          <path d="M 322 380 L 342 360 L 350 368 L 330 388 Z" fill="#8a8a8a" />
          <g transform="rotate(-38 318 372)">
            <ellipse cx="318" cy="372" rx="13" ry="34" fill="#1d1d1d" />
            <ellipse cx="318" cy="372" rx="9" ry="28" fill="#2b2b2b" />
            <ellipse cx="318" cy="372" rx="4.5" ry="12" fill="#161616" />
          </g>
          <path d="M 158 500 L 322 376 L 332 388 L 168 512 Z" fill="#171717" />
          <g fill="#dad3c4" opacity="0.92" transform="rotate(-37 245 444)">
            <rect x="-86" y="-7" width="11" height="14" rx="2" />
            <rect x="-66" y="-7" width="11" height="14" rx="2" />
            <rect x="-46" y="-7" width="11" height="14" rx="2" />
            <rect x="-26" y="-7" width="11" height="14" rx="2" />
            <rect x="-6" y="-7" width="11" height="14" rx="2" />
            <rect x="14" y="-7" width="11" height="14" rx="2" />
          </g>
          <circle cx="245" cy="444" r="3.6" fill="#C9A24B" />
          <path
            d="M 152 504 L 168 512 L 162 520 C 156 524 148 520 147 513 C 146 508 148 505 152 504 Z"
            fill="#1d1d1d"
          />
        </g>
        <g transform="translate(680,0) scale(-1,1)">
          <path
            d="M 150 506 L 330 372 L 340 385 L 160 519 C 153 524 144 521 142 513 C 141 510 144 508 150 506 Z"
            fill="#1f1b16"
          />
          <path d="M 322 378 L 340 365 L 348 376 L 330 389 Z" fill="#352f26" />
          <path
            d="M 142 513 C 141 510 144 508 150 506 L 158 512 C 152 514 149 518 151 522 C 146 522 143 518 142 513 Z"
            fill="#352f26"
          />
          <path d="M 330 372 L 506 178 L 514 187 L 340 385 Z" fill="#161616" />
          <path d="M 332 374 L 505 182 L 509 186 L 336 379 Z" fill="#d4d4d4" />
          <path
            d="M 338 383 L 512 190"
            stroke="#ffffff"
            strokeWidth="1.4"
            opacity="0.8"
            fill="none"
            strokeLinecap="round"
          />
          <path d="M 506 178 L 524 158 L 520 182 L 514 187 Z" fill="#161616" />
          <path d="M 507 180 L 523 160 L 519 180 Z" fill="#dedede" />
          <path d="M 322 380 L 342 360 L 350 368 L 330 388 Z" fill="#828282" />
          <g transform="rotate(-38 318 372)">
            <ellipse cx="318" cy="372" rx="13" ry="34" fill="#1a1a1a" />
            <ellipse cx="318" cy="372" rx="9" ry="28" fill="#282828" />
            <ellipse cx="318" cy="372" rx="4.5" ry="12" fill="#141414" />
          </g>
          <path d="M 158 500 L 322 376 L 332 388 L 168 512 Z" fill="#141414" />
          <g fill="#d2cbbc" opacity="0.92" transform="rotate(-37 245 444)">
            <rect x="-86" y="-7" width="11" height="14" rx="2" />
            <rect x="-66" y="-7" width="11" height="14" rx="2" />
            <rect x="-46" y="-7" width="11" height="14" rx="2" />
            <rect x="-26" y="-7" width="11" height="14" rx="2" />
            <rect x="-6" y="-7" width="11" height="14" rx="2" />
            <rect x="14" y="-7" width="11" height="14" rx="2" />
          </g>
          <circle cx="245" cy="444" r="3.6" fill="#C9A24B" />
          <path
            d="M 152 504 L 168 512 L 162 520 C 156 524 148 520 147 513 C 146 508 148 505 152 504 Z"
            fill="#1a1a1a"
          />
        </g>
        <path
          d="M 86 138 Q 150 158 210 140"
          fill="none"
          stroke="#4a3b32"
          strokeWidth="3"
          opacity="0.75"
          strokeLinecap="round"
        />
        <use href="#lm_bloom" transform="translate(106,146) scale(1.5) rotate(-10)" />
        <use href="#lm_bloom" transform="translate(152,132) scale(1.2) rotate(25)" />
        <use href="#lm_bloom" transform="translate(476,474) scale(1.15) rotate(15)" />
        <use href="#lm_bloom" transform="translate(522,452) scale(0.85) rotate(-25)" />
        <use href="#lm_bloom" transform="translate(516,250) scale(0.62) rotate(-18)" />
        <use href="#lm_petal" transform="translate(545,330) scale(0.65) rotate(70)" />
        <use href="#lm_petal" transform="translate(126,300) scale(0.6) rotate(110)" />
      </g>
      <circle
        cx="340"
        cy="340"
        r="294"
        fill="none"
        stroke="#C2362A"
        strokeWidth="1.4"
        opacity="0.35"
      />
    </svg>
  );
}
