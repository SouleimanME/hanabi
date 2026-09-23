/** Coquille de la boutique : etat partage, cablage des hooks, choix de l'ecran. */
import { Suspense, lazy, useState, useCallback, useRef, useEffect, useMemo } from "react";

import { translator } from "./i18n/index.js";
import { I18nProvider } from "./i18n/context.jsx";
import { createPriceFormatter } from "./lib/format.js";
import { Products, Promos, Orders, nouvelleCleIdempotence } from "./lib/api.js";

import { useLocalStorageState } from "./hooks/useLocalStorageState.js";
import { useTheme } from "./hooks/useTheme.js";
import { useDebouncedValue } from "./hooks/useDebouncedValue.js";
import { useToast } from "./hooks/useToast.js";
import { useEscapeKey } from "./hooks/useEscapeKey.js";
import { useCatalog } from "./hooks/useCatalog.js";
import { useCart, ADD_RESULT } from "./hooks/useCart.js";
import { useSaved } from "./hooks/useSaved.js";
import { usePricing } from "./hooks/usePricing.js";
import { useAuth } from "./hooks/useAuth.js";
import { useUrlSync } from "./hooks/useUrlSync.js";
import { useVerrouDefilement } from "./hooks/useVerrouDefilement.js";
import { useChangementDEcran } from "./hooks/useChangementDEcran.js";
import { useFonctionStable } from "./hooks/useFonctionStable.js";

import { Header } from "./components/layout/Header.jsx";
import { Footer } from "./components/layout/Footer.jsx";
import { MenuSheet } from "./components/layout/MenuSheet.jsx";
import { CartDrawer } from "./components/cart/CartDrawer.jsx";
import { AuthModal } from "./components/modals/AuthModal.jsx";
import { LegalModal } from "./components/modals/LegalModal.jsx";
import { BandeauCookies } from "./components/consent/BandeauCookies.jsx";
import { PreferencesCookies } from "./components/consent/PreferencesCookies.jsx";
import { enregistrerChoix, useConsentement } from "./lib/consentement.js";
import { Toast } from "./components/ui/Toast.jsx";

import Home from "./pages/Home.jsx";
import ProductPage from "./pages/ProductPage.jsx";
import Wishlist from "./pages/Wishlist.jsx";
import Saved from "./pages/Saved.jsx";
import Account from "./pages/Account.jsx";
import Confirmation from "./pages/Confirmation.jsx";
import ConfirmerAdresse from "./pages/ConfirmerAdresse.jsx";
import NouveauMotDePasse from "./pages/NouveauMotDePasse.jsx";
import Desinscription from "./pages/Desinscription.jsx";

// Le paiement (formulaire, adresses, logos des cartes) ne pèse pas sur
// l'accueil : il se charge à l'ouverture du panier, avant le clic qui y mène
const chargerPaiement = () => import("./pages/Checkout.jsx");
const Checkout = lazy(chargerPaiement);

import "./styles/index.css";

const RECENTLY_VIEWED_MAX = 8;

/** Titre d'onglet de chaque écran, sans la marque. `null` : l'accueil tel quel. */
function titreDeLEcran(view, t, fiche, categorie) {
  switch (view) {
    case "product":
      return fiche?.name ?? null;
    case "home":
      return categorie !== "Tout" ? t("cat_" + categorie) : null;
    case "wishlist":
      return t("favs");
    case "saved":
      return t("saved");
    case "account":
      return t("myAccount");
    case "checkout":
      return t("payment");
    case "done":
      return t("confirmed");
    case "verifyEmail":
      return t("pageVerify");
    case "resetPassword":
      return t("resetTitle");
    case "unsubscribe":
      return t("pageUnsub");
    default:
      return null;
  }
}

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const [lang, setLang] = useLocalStorageState("lang", "fr");
  const [wishlist, setWishlist] = useLocalStorageState("wishlist", []);
  const [recentIds, setRecentIds] = useLocalStorageState("recent", []);

  const [category, setCategory] = useState("Tout");
  const [sort, setSort] = useState("pop");
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query);

  const [view, setView] = useState("home");
  const [accountSection, setAccountSection] = useState(null);
  const [activeProduct, setActiveProduct] = useState(null);
  // null tant que les avis ne sont pas arrivés : la fiche ne dit pas « aucun avis » à tort
  const [activeReviews, setActiveReviews] = useState(null);
  const [cartOpen, setCartOpen] = useState(false);
  useEffect(() => {
    if (cartOpen) chargerPaiement();
  }, [cartOpen]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [legalPage, setLegalPage] = useState(null);
  const choixCookies = useConsentement();
  const [prefsCookies, setPrefsCookies] = useState(false);
  const [lastOrder, setLastOrder] = useState(null);
  const gridRef = useRef(null);

  const t = useMemo(() => translator(lang), [lang]);
  const eur = useMemo(() => createPriceFormatter(lang), [lang]);
  const { toast, show: flash, runAction } = useToast();

  // La langue de la page suit celle de l'interface : lecteurs d'ecran,
  // cesure et noms de mois en dependent.
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const {
    catalog,
    products,
    featured,
    error: loadError,
    loading,
    refreshing,
    reload,
    remember,
  } = useCatalog({ category, query: debouncedQuery, sort, lang });

  const cart = useCart(catalog);
  const saved = useSaved();
  const [promo, setPromo] = useState(null);

  const onPromoRejected = useCallback(
    (message) => {
      setPromo(null);
      flash(message);
    },
    [flash],
  );
  const pricing = usePricing(cart.items, promo, cart.subtotalCents, onPromoRejected);

  const {
    user,
    orders,
    login,
    signup,
    logout,
    refreshOrders,
    refreshUser,
    adopterSession,
    poserProfil,
  } = useAuth();

  useEscapeKey(
    useCallback(() => {
      setCartOpen(false);
      setMenuOpen(false);
      setAuthOpen(false);
      setLegalPage(null);
      setPrefsCookies(false);
    }, []),
  );

  useEffect(() => {
    if (view === "account" && user) refreshOrders();
  }, [view, user, refreshOrders]);

  // --- Catalogue et fiche produit ---

  // Fiche demandee en dernier : une reponse lente pour une fiche quittee entre-temps
  // ne doit pas remplacer celle qu'on regarde.
  const ficheDemandee = useRef(null);

  const openProduct = useCallback(
    async (product) => {
      ficheDemandee.current = product.id;
      setActiveProduct(product);
      setActiveReviews(null);
      setView("product");
      window.scrollTo(0, 0);
      setRecentIds((ids) =>
        [product.id, ...ids.filter((id) => id !== product.id)].slice(0, RECENTLY_VIEWED_MAX),
      );

      try {
        const [detail, reviews] = await Promise.all([
          Products.get(product.id, lang),
          Products.reviews(product.id),
        ]);
        if (ficheDemandee.current !== product.id) return;
        setActiveProduct(detail);
        setActiveReviews(reviews);
        remember([detail]);
      } catch {
        // La fiche reste affichée avec les données de la grille, sans avis en attente
        if (ficheDemandee.current === product.id) setActiveReviews((r) => r ?? []);
      }
    },
    [lang, remember, setRecentIds],
  );

  /** Ouvre une fiche depuis son seul identifiant : lien partage, favori du
   *  navigateur, bouton Retour. */
  const openProductById = useCallback(
    async (id) => {
      const known = catalog[id];
      if (known) {
        openProduct(known);
        return;
      }
      try {
        openProduct(await Products.get(id, lang));
      } catch {
        setView("home");
      }
    },
    [catalog, lang, openProduct],
  );

  // Jeton ou lien signe lus dans l'URL pour les ecrans atteints depuis un
  // courriel ; `useUrlSync` les efface de la barre d'adresse des qu'on les quitte.
  const [jetonUrl, setJetonUrl] = useState(null);
  const [lienDesinscription, setLienDesinscription] = useState(null);

  useUrlSync({
    view,
    setView,
    activeProduct,
    openProductById,
    onJeton: setJetonUrl,
    onLien: setLienDesinscription,
  });

  // Revenir sur la confirmation apres coup n'a pas de sens : la commande n'est
  // plus en memoire.
  useEffect(() => {
    if (view === "done" && !lastOrder) setView("home");
  }, [view, lastOrder]);

  // Nom et description sont traduits cote serveur : un changement de langue
  // recharge la fiche ouverte.
  useEffect(() => {
    if (view !== "product" || !activeProduct) return;
    let cancelled = false;
    (async () => {
      try {
        const [detail, reviews] = await Promise.all([
          Products.get(activeProduct.id, lang),
          Products.reviews(activeProduct.id),
        ]);
        if (cancelled || ficheDemandee.current !== detail.id) return;
        setActiveProduct(detail);
        setActiveReviews(reviews);
      } catch {
        /* on garde la version precedente */
      }
    })();
    return () => {
      cancelled = true;
    };
    // Limite a `lang` : dependre de `activeProduct` relancerait l'appel en boucle
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  // Identité fixe : ajouter un article ne fait pas re-rendre toute la grille
  const addToCart = useFonctionStable((id, qty = 1) => {
    const result = cart.add(id, qty);
    if (result === ADD_RESULT.ADDED) flash(t("tAdded"));
    else if (result === ADD_RESULT.MAX_STOCK) flash(t("tMaxStock"));
  });

  const submitReview = useCallback(
    async (productId, rating, text, antibot) => {
      try {
        await Products.addReview(productId, rating, text, antibot);
        flash(t("tThanks"));
        const [detail, reviews] = await Promise.all([
          Products.get(productId, lang),
          Products.reviews(productId),
        ]);
        setActiveProduct(detail);
        setActiveReviews(reviews);
        remember([detail]);
        return null;
      } catch (e) {
        // Sentinelle lue par ProductPage pour ouvrir la connexion
        return e.status === 401 ? "login" : e.message;
      }
    },
    [flash, lang, remember, t],
  );

  const requestRestockAlert = useCallback(
    async (productId, email, antibot) => {
      try {
        await Products.notify(productId, email, antibot, lang);
        flash(t("notifyOk"));
        return null;
      } catch (e) {
        return e.message;
      }
    },
    [flash, lang, t],
  );

  // --- Panier et commande ---

  /** Retirer se defait depuis la notification : pas de confirmation. */
  const removeFromCart = useCallback(
    (id) => {
      const ligne = cart.lines.find((l) => l.id === id);
      cart.remove(id);
      if (ligne) {
        flash(t("tRemoved", { name: ligne.product.name }), {
          label: t("undo"),
          run: () => cart.add(id, ligne.qty),
        });
      }
    },
    [cart, flash, t],
  );

  const saveForLater = useCallback(
    (id) => {
      cart.remove(id);
      saved.save(id);
      flash(t("tSaved"));
    },
    [cart, saved, flash, t],
  );

  const moveToCart = useCallback(
    (id) => {
      // On ne retire des enregistres que si le panier a accepte l'article : un
      // produit epuise entre-temps ne doit se retrouver nulle part.
      const result = cart.add(id);
      if (result !== ADD_RESULT.ADDED) {
        flash(result === ADD_RESULT.MAX_STOCK ? t("tMaxStock") : t("soldNow"));
        return;
      }
      saved.remove(id);
      flash(t("tAdded"));
    },
    [cart, saved, flash, t],
  );

  const toggleWish = useCallback(
    (id) => setWishlist((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id])),
    [setWishlist],
  );

  const applyPromo = useCallback(
    async (raw) => {
      const code = raw.trim().toUpperCase();
      if (!code) return t("errPromoEmpty");
      try {
        await Promos.validate(code, pricing.subtotal_cents);
        setPromo(code);
        flash(t("tPromo", { code }));
        return null;
      } catch (e) {
        return e.message;
      }
    },
    [flash, pricing.subtotal_cents, t],
  );

  // Cle d'idempotence de l'achat en cours
  const cleAchat = useRef(null);

  const placeOrder = useCallback(
    async (form) => {
      if (!cleAchat.current) cleAchat.current = nouvelleCleIdempotence();

      const order = await Orders.checkout(
        {
          items: cart.toPayload(),
          email: form.email,
          shipping: {
            prenom: form.prenom,
            nom: form.nom,
            adresse: form.adresse,
            cp: form.cp,
            ville: form.ville,
          },
          promo_code: promo,
          // Carte enregistree : le serveur retrouve son jeton depuis
          // l'identifiant, apres avoir verifie son titulaire. Nouvelle carte :
          // un jeton tire du numero, qui ne quitte pas le navigateur.
          payment_method_id: form.payment_method_id ?? null,
          payment_token: form.payment_token ?? null,
          // Corps construit champ par champ : un champ ajoute a l'ecran doit
          // aussi l'etre ici.
          cgv_acceptees: form.cgv_acceptees === true,
        },
        cleAchat.current,
      );

      cleAchat.current = null;
      setLastOrder(order);
      cart.clear();
      setPromo(null);
      setView("done");
      window.scrollTo(0, 0);
      reload();
      if (user) refreshOrders();
      return order;
    },
    [cart, promo, reload, refreshOrders, user],
  );

  // --- Navigation ---

  // Retour qui garde les filtres, pour les boutons « Retour » des ecrans internes
  const goHome = useCallback(() => setView("home"), []);

  /** Accueil tel qu'on le decouvre : categorie et recherche remises a zero. */
  const resetToHome = useCallback(() => {
    setView("home");
    setCategory("Tout");
    setQuery("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const goCategory = useCallback((next) => {
    setCategory(next);
    setView("home");
    // Attend le rendu de la grille avant d'y descendre
    setTimeout(() => gridRef.current?.scrollIntoView({ behavior: "smooth" }), 0);
  }, []);

  const goAccount = useCallback(() => (user ? setView("account") : setAuthOpen(true)), [user]);

  /** Ouvre le compte sur une section. L'horodatage rejoue le recentrage si l'on
   *  demande deux fois la meme. */
  const goAccountSection = useCallback(
    (name) => {
      if (!user) {
        setAuthOpen(true);
        return;
      }
      setAccountSection({ name, at: Date.now() });
      setView("account");
    },
    [user],
  );

  const goSaved = useCallback(() => {
    setCartOpen(false);
    setView("saved");
    window.scrollTo(0, 0);
  }, []);

  const goCheckout = useCallback(() => {
    setCartOpen(false);
    setView("checkout");
    window.scrollTo(0, 0);
  }, []);

  const handleLogin = useCallback(
    async (credentials) => {
      const { user: signedIn, error } = await login(credentials);
      if (signedIn) flash(t("tBack", { name: signedIn.name }));
      return error;
    },
    [flash, login, t],
  );

  const handleSignup = useCallback(
    async (payload) => {
      const { user: created, error } = await signup(payload);
      if (created) flash(t("tWelcome", { name: created.name }));
      return error;
    },
    [flash, signup, t],
  );

  const handleLogout = useCallback(() => {
    logout();
    setView("home");
    flash(t("tLogout"));
  }, [flash, logout, t]);

  const isWished = useCallback((id) => wishlist.includes(id), [wishlist]);
  const byId = useCallback((ids) => ids.map((id) => catalog[id]).filter(Boolean), [catalog]);

  // Piece du mois : le premier produit mis en avant depuis le back-office, a
  // defaut la premiere nouveaute.
  const piece = featured[0] ?? products.find((p) => p.is_new) ?? null;
  const fenetreOuverte = cartOpen || menuOpen || authOpen || Boolean(legalPage) || prefsCookies;
  const bandeauCookies = choixCookies === null && !fenetreOuverte;

  useVerrouDefilement(fenetreOuverte);
  useChangementDEcran(
    view === "product" ? `product-${activeProduct?.id}` : view,
    titreDeLEcran(view, t, activeProduct, category),
    t("siteTagline"),
  );

  // Même famille, pris dans tout le catalogue : la grille filtrée par une
  // recherche n'en montrait parfois aucun.
  const memeFamille = activeProduct
    ? Object.values(catalog)
        .filter((x) => x.category === activeProduct.category && x.id !== activeProduct.id)
        .slice(0, 4)
    : [];

  return (
    <I18nProvider t={t}>
      <div className="shop">
        <a className="skip-link" href="#contenu">
          {t("skipToContent")}
        </a>

        {/* Premier dans l'ordre du clavier, affiché en bas de l'écran */}
        {bandeauCookies && (
          <BandeauCookies
            onAccepter={() => enregistrerChoix({ audience: true })}
            onRefuser={() => enregistrerChoix({ audience: false })}
            onPersonnaliser={() => setPrefsCookies(true)}
            onEnSavoirPlus={() => setLegalPage("cookies")}
          />
        )}

        <div className="page-shell" inert={fenetreOuverte ? "" : undefined}>
          <Header
            lang={lang}
            onLangChange={setLang}
            theme={theme}
            onToggleTheme={toggleTheme}
            user={user}
            cartCount={cart.count}
            wishlistCount={wishlist.length}
            showSearch={view === "home"}
            query={query}
            onQueryChange={setQuery}
            onGoHome={resetToHome}
            onGoWishlist={() => setView("wishlist")}
            onGoAccount={() => setView("account")}
            onOpenAuth={() => setAuthOpen(true)}
            onOpenCart={() => setCartOpen(true)}
            onOpenMenu={() => setMenuOpen(true)}
          />

          {view === "home" && (
            <Home
              ref={gridRef}
              products={products}
              featured={piece}
              loadErr={loadError}
              onOpen={openProduct}
              onAdd={addToCart}
              cat={category}
              onCategoryChange={setCategory}
              query={debouncedQuery}
              onClearQuery={() => {
                setQuery("");
                setCategory("Tout");
              }}
              sort={sort}
              setSort={setSort}
              wished={isWished}
              onWish={toggleWish}
              recent={byId(recentIds).slice(0, 5)}
              loading={loading}
              refreshing={refreshing}
              eur={eur}
            />
          )}

          {view === "product" && activeProduct && (
            <ProductPage
              p={activeProduct}
              reviews={activeReviews}
              onBack={goHome}
              onAddItem={addToCart}
              onOpenCart={() => setCartOpen(true)}
              canReview={!!user}
              onReview={submitReview}
              onAskLogin={() => setAuthOpen(true)}
              onNotify={requestRestockAlert}
              wished={isWished(activeProduct.id)}
              onWish={() => toggleWish(activeProduct.id)}
              onOpen={openProduct}
              related={memeFamille}
              lang={lang}
              eur={eur}
            />
          )}

          {view === "wishlist" && (
            <Wishlist
              items={byId(wishlist)}
              onOpen={openProduct}
              onAdd={addToCart}
              onWish={toggleWish}
              onBack={goHome}
              eur={eur}
            />
          )}

          {view === "saved" && (
            <Saved
              items={byId(saved.ids)}
              onOpen={openProduct}
              onMoveToCart={moveToCart}
              onRemove={saved.remove}
              onBack={goHome}
              eur={eur}
            />
          )}

          {view === "account" &&
            (user ? (
              <Account
                user={user}
                orders={orders}
                section={accountSection}
                onLogout={handleLogout}
                onBack={goHome}
                eur={eur}
                onProfil={poserProfil}
                onEfface={(resultat) => {
                  // Le compte n'existe plus, la session non plus
                  handleLogout();
                  flash(resultat?.message || t("rgpdDeleteDone"));
                }}
                flash={flash}
              />
            ) : (
              <main id="contenu" className="wrap page">
                <div className="empty">
                  <p>{t("loginToSee")}</p>
                  <button className="btn btn-primary" onClick={() => setAuthOpen(true)}>
                    {t("signin")}
                  </button>
                </div>
              </main>
            ))}

          {view === "checkout" && (
            <Suspense fallback={<main id="contenu" className="wrap page" aria-busy="true" />}>
              <Checkout
                lines={cart.lines}
                disp={pricing}
                promo={promo}
                promoLabel={pricing.promo?.label ?? null}
                onApplyPromo={applyPromo}
                onClearPromo={() => setPromo(null)}
                user={user}
                onBack={goHome}
                onPay={placeOrder}
                onOpenLegal={setLegalPage}
                empty={cart.lines.length === 0}
                lang={lang}
                eur={eur}
              />
            </Suspense>
          )}

          {view === "done" && lastOrder && (
            <Confirmation
              order={lastOrder}
              onContinue={() => {
                setLastOrder(null);
                setView("home");
              }}
              loggedIn={!!user}
              onAccount={() => setView("account")}
              eur={eur}
            />
          )}

          {view === "verifyEmail" && (
            <ConfirmerAdresse
              jeton={jetonUrl}
              loggedIn={!!user}
              onConfirme={refreshUser}
              onContinue={resetToHome}
              onSeConnecter={() => {
                setView("home");
                setAuthOpen(true);
              }}
            />
          )}

          {view === "resetPassword" && (
            <NouveauMotDePasse
              jeton={jetonUrl}
              onReussite={(session) => {
                adopterSession(session);
                flash(t("resetOkToast"));
                setView("account");
              }}
              onContinue={resetToHome}
            />
          )}

          {view === "unsubscribe" && (
            <Desinscription lien={lienDesinscription} onContinue={resetToHome} />
          )}

          <Footer
            lang={lang}
            onGoCategory={goCategory}
            onOpenLegal={setLegalPage}
            onManageCookies={() => setPrefsCookies(true)}
          />
        </div>

        <MenuSheet
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
          user={user}
          view={view}
          lang={lang}
          onLangChange={setLang}
          theme={theme}
          onToggleTheme={toggleTheme}
          wishlistCount={wishlist.length}
          savedCount={saved.count}
          category={category}
          onGoCategory={goCategory}
          onGoHome={resetToHome}
          onGoWishlist={() => setView("wishlist")}
          onGoSaved={goSaved}
          onGoAccount={goAccount}
          onGoOrders={() => goAccountSection("orders")}
          onGoInfo={() => goAccountSection("infos")}
          onOpenLegal={setLegalPage}
        />

        <CartDrawer
          open={cartOpen}
          onClose={() => setCartOpen(false)}
          lines={cart.lines}
          disp={pricing}
          onQty={cart.setQty}
          onRemove={removeFromCart}
          onCheckout={goCheckout}
          promo={promo}
          promoLabel={pricing.promo?.label ?? null}
          onApplyPromo={applyPromo}
          onClearPromo={() => setPromo(null)}
          savedCount={saved.count}
          onSaveForLater={saveForLater}
          onGoSaved={goSaved}
          lang={lang}
          eur={eur}
        />

        {authOpen && (
          <AuthModal
            onClose={() => setAuthOpen(false)}
            onLogin={handleLogin}
            onSignup={handleSignup}
          />
        )}

        {legalPage && (
          <LegalModal page={legalPage} lang={lang} onClose={() => setLegalPage(null)} />
        )}

        {prefsCookies && (
          <PreferencesCookies
            choix={choixCookies}
            onEnregistrer={(choix) => {
              enregistrerChoix(choix);
              setPrefsCookies(false);
              flash(t("consentSaved"));
            }}
            onClose={() => setPrefsCookies(false)}
            onEnSavoirPlus={() => {
              setPrefsCookies(false);
              setLegalPage("cookies");
            }}
          />
        )}

        <Toast toast={toast} onAction={runAction} />
      </div>
    </I18nProvider>
  );
}
