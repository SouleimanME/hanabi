/** Coquille de la boutique.
 *
 * Ce composant ne dessine presque rien : il tient l'etat partage, cable les
 * hooks metier entre eux et choisit l'ecran a afficher. Tout le rendu est
 * delegue a `components/` et `pages/`.
 *
 * Navigation : un simple etat `view` plutot qu'un routeur. La boutique compte
 * six ecrans sans navigation profonde ; ajouter react-router couterait une
 * dependance pour un besoin que couvrent une table de correspondance
 * (`lib/routes.js`) et un hook de synchronisation (`useUrlSync`).
 *
 * L'etat reste la source de verite du rendu ; l'URL le suit dans les deux sens.
 * Les fiches produit sont donc partageables et memorisables, et les boutons
 * Retour et Suivant du navigateur parcourent les ecrans.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import { User } from "lucide-react";

import { translator } from "./i18n/index.js";
import { I18nProvider } from "./i18n/context.jsx";
import { createPriceFormatter } from "./lib/format.js";
import { Products, Promos, Orders } from "./lib/api.js";

import { useLocalStorageState } from "./hooks/useLocalStorageState.js";
import { useTheme } from "./hooks/useTheme.js";
import { useDebouncedValue } from "./hooks/useDebouncedValue.js";
import { useToast } from "./hooks/useToast.js";
import { useHideOnScroll } from "./hooks/useHideOnScroll.js";
import { useEscapeKey } from "./hooks/useEscapeKey.js";
import { useCatalog } from "./hooks/useCatalog.js";
import { useCart, ADD_RESULT } from "./hooks/useCart.js";
import { useSaved } from "./hooks/useSaved.js";
import { usePricing } from "./hooks/usePricing.js";
import { useAuth } from "./hooks/useAuth.js";
import { useUrlSync } from "./hooks/useUrlSync.js";
import { useWelcomeOffer } from "./hooks/useWelcomeOffer.js";

import { Header } from "./components/layout/Header.jsx";
import { Footer } from "./components/layout/Footer.jsx";
import { MobileNav } from "./components/layout/MobileNav.jsx";
import { MenuSheet } from "./components/layout/MenuSheet.jsx";
import { DropCountdown } from "./components/layout/DropCountdown.jsx";
import { CartDrawer } from "./components/cart/CartDrawer.jsx";
import { AuthModal } from "./components/modals/AuthModal.jsx";
import { LegalModal } from "./components/modals/LegalModal.jsx";
import { WelcomeOffer } from "./components/modals/WelcomeOffer.jsx";
import { Toast } from "./components/ui/Toast.jsx";

import Home from "./pages/Home.jsx";
import ProductPage from "./pages/ProductPage.jsx";
import Wishlist from "./pages/Wishlist.jsx";
import Saved from "./pages/Saved.jsx";
import Account from "./pages/Account.jsx";
import Checkout from "./pages/Checkout.jsx";
import Confirmation from "./pages/Confirmation.jsx";

import "./styles/index.css";

const RECENTLY_VIEWED_MAX = 8;

export default function App() {
  // --- Preferences persistantes ---
  // Le theme suit le reglage du systeme tant que personne n'a touche au bouton.
  const [theme, toggleTheme] = useTheme();
  const [lang, setLang] = useLocalStorageState("lang", "fr");
  const [wishlist, setWishlist] = useLocalStorageState("wishlist", []);
  const [recentIds, setRecentIds] = useLocalStorageState("recent", []);

  // --- Filtres du catalogue ---
  const [category, setCategory] = useState("Tout");
  const [sort, setSort] = useState("pop");
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebouncedValue(query);

  // --- Navigation et fenetres ---
  const [view, setView] = useState("home");
  // Section du compte a mettre en avant : le menu y mene directement.
  const [accountSection, setAccountSection] = useState(null);
  const [activeProduct, setActiveProduct] = useState(null);
  const [activeReviews, setActiveReviews] = useState([]);
  const [cartOpen, setCartOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [legalPage, setLegalPage] = useState(null);
  const [lastOrder, setLastOrder] = useState(null);
  const gridRef = useRef(null);

  const t = translator(lang);
  const eur = createPriceFormatter(lang);
  const { message: toast, show: flash } = useToast();
  // L'en-tete est pilote par sa ref, sans etat React : `useHideOnScroll` pose
  // lui-meme les classes de defilement sur le noeud. Le retour a `useState`
  // re-rendrait toute l'application a chaque cran de molette.
  const headerRef = useRef(null);
  useHideOnScroll(headerRef);

  const {
    catalog,
    products,
    featured,
    error: loadError,
    loading,
    refreshing,
    reload,
    remember,
  } = useCatalog({
    category,
    query: debouncedQuery,
    sort,
    lang,
  });

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

  const { user, orders, login, signup, logout, refreshOrders } = useAuth();

  // Offre de bienvenue : ni pendant la commande, ou toute interruption coute
  // une vente, ni pour un client connecte, qui a deja franchi le pas.
  const welcome = useWelcomeOffer(!user && view !== "checkout" && view !== "done");

  useEscapeKey(
    useCallback(() => {
      setCartOpen(false);
      setMenuOpen(false);
      setAuthOpen(false);
      setLegalPage(null);
    }, []),
  );

  useEffect(() => {
    if (view === "account" && user) refreshOrders();
  }, [view, user, refreshOrders]);

  // --- Catalogue et fiche produit ---

  const openProduct = useCallback(
    async (product) => {
      setActiveProduct(product);
      setActiveReviews([]);
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
        setActiveProduct(detail);
        setActiveReviews(reviews);
        remember([detail]);
      } catch {
        /* la fiche reste affichee avec les donnees de la grille */
      }
    },
    [lang, remember, setRecentIds],
  );

  /** Ouvre une fiche a partir de son seul identifiant.
   *
   * Necessaire pour les arrivees par URL (lien partage, favori du navigateur,
   * bouton Retour) : on ne dispose alors que de l'identifiant, pas de l'objet
   * produit que la grille passe habituellement.
   */
  const openProductById = useCallback(
    async (id) => {
      const known = catalog[id];
      if (known) {
        openProduct(known);
        return;
      }
      try {
        const detail = await Products.get(id, lang);
        openProduct(detail);
      } catch {
        // Identifiant inconnu ou API muette : on ne laisse pas un ecran vide.
        setView("home");
      }
    },
    [catalog, lang, openProduct],
  );

  useUrlSync({ view, setView, activeProduct, openProductById });

  // Revenir sur l'ecran de confirmation apres coup n'a pas de sens : la
  // commande n'est plus en memoire, et la page serait vide.
  useEffect(() => {
    if (view === "done" && !lastOrder) setView("home");
  }, [view, lastOrder]);

  // La fiche ouverte doit suivre le changement de langue : nom et description
  // sont traduits cote serveur, il faut donc la recharger.
  useEffect(() => {
    if (view !== "product" || !activeProduct) return;
    let cancelled = false;
    (async () => {
      try {
        const [detail, reviews] = await Promise.all([
          Products.get(activeProduct.id, lang),
          Products.reviews(activeProduct.id),
        ]);
        if (cancelled) return;
        setActiveProduct(detail);
        setActiveReviews(reviews);
      } catch {
        /* on garde la version precedente */
      }
    })();
    return () => {
      cancelled = true;
    };
    // Volontairement limite a `lang` : se declencher sur `activeProduct`
    // relancerait l'appel en boucle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  const addToCart = useCallback(
    (id, qty = 1) => {
      const result = cart.add(id, qty);
      if (result === ADD_RESULT.ADDED) flash(t("tAdded"));
      else if (result === ADD_RESULT.MAX_STOCK) flash(t("tMaxStock"));
    },
    [cart, flash, t],
  );

  // `antibot` est fourni par le formulaire appelant : chaque formulaire tient
  // son propre defi, calcule pendant la saisie.
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
        // Sentinelle lue par ProductPage pour ouvrir la fenetre de connexion.
        return e.status === 401 ? "login" : e.message;
      }
    },
    [flash, lang, remember, t],
  );

  const requestRestockAlert = useCallback(
    async (productId, email, antibot) => {
      try {
        await Products.notify(productId, email, antibot);
        flash(t("notifyOk"));
        return null;
      } catch (e) {
        return e.message;
      }
    },
    [flash, t],
  );

  // --- Panier et commande ---

  /** Sort un article du panier sans le perdre de vue (voir hooks/useSaved.js). */
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
      // On ne retire des enregistres que si le panier a bien accepte l'article :
      // un produit epuise entre-temps resterait sinon nulle part.
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

  const placeOrder = useCallback(
    async (form) => {
      const order = await Orders.checkout({
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
      });
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

  // Retour a l'accueil qui conserve les filtres : utilise par les boutons
  // « Retour » des ecrans internes, ou perdre sa recherche serait une punition.
  const goHome = useCallback(() => setView("home"), []);

  /** Retour a l'accueil « propre », comme un clic sur le logo d'un site.
   *
   * Le logo et l'onglet Boutique promettent la page d'accueil telle qu'on la
   * decouvre : on remet donc la categorie et la recherche a zero, et on
   * repart du haut. Sans cela, cliquer sur le logo depuis une recherche
   * infructueuse ramenait sur une grille vide, au milieu de la page. */
  const resetToHome = useCallback(() => {
    setView("home");
    setCategory("Tout");
    setQuery("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);
  const goCategory = useCallback((next) => {
    setCategory(next);
    setView("home");
    // Attend le rendu de la grille avant de faire defiler jusqu'a elle.
    setTimeout(() => gridRef.current?.scrollIntoView({ behavior: "smooth" }), 0);
  }, []);
  const goAccount = useCallback(() => (user ? setView("account") : setAuthOpen(true)), [user]);

  /** Ouvre le compte sur une section donnee (« infos » ou « orders »).
   *
   * La cle change a chaque appel meme si la section est la meme : sans elle,
   * demander deux fois « Mes commandes » depuis le menu ne rejouerait pas le
   * recentrage, et le second clic paraitrait sans effet. */
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

  return (
    <I18nProvider t={t}>
      <div className={"root" + (theme === "dark" ? " dark" : "")}>
        <Header
          ref={headerRef}
          lang={lang}
          onLangChange={setLang}
          theme={theme}
          onToggleTheme={toggleTheme}
          user={user}
          cartCount={cart.count}
          wishlistCount={wishlist.length}
          showFilters={view === "home"}
          query={query}
          onQueryChange={setQuery}
          category={category}
          onCategoryChange={goCategory}
          onGoHome={resetToHome}
          onGoWishlist={() => setView("wishlist")}
          onGoAccount={() => setView("account")}
          onOpenAuth={() => setAuthOpen(true)}
          onOpenCart={() => setCartOpen(true)}
          onOpenMenu={() => setMenuOpen(true)}
        />

        {view === "home" && <DropCountdown />}

        {/* `key={view}` remonte le conteneur a chaque changement d'ecran, ce qui
            rejoue l'animation d'entree definie par `.view`. */}
        <div className="view" key={view}>
          {view === "home" && (
            <Home
              ref={gridRef}
              products={products}
              featuredList={featured}
              loadErr={loadError}
              onOpen={openProduct}
              onAdd={addToCart}
              cat={category}
              query={debouncedQuery}
              sort={sort}
              setSort={setSort}
              wished={isWished}
              onWish={toggleWish}
              recent={byId(recentIds).slice(0, 5)}
              featured={catalog[2]}
              loading={loading}
              refreshing={refreshing}
              theme={theme}
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
              related={products
                .filter((x) => x.category === activeProduct.category && x.id !== activeProduct.id)
                .slice(0, 3)}
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
              />
            ) : (
              <main className="pp">
                <div className="state">
                  <User size={32} strokeWidth={1.3} />
                  <p>{t("loginToSee")}</p>
                  <button className="btn-primary" onClick={() => setAuthOpen(true)}>
                    {t("signin")}
                  </button>
                </div>
              </main>
            ))}

          {view === "checkout" && (
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
              empty={cart.lines.length === 0}
              lang={lang}
              eur={eur}
            />
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
        </div>

        <Footer onGoCategory={goCategory} onOpenLegal={setLegalPage} />

        <MobileNav
          view={view}
          cartCount={cart.count}
          wishlistCount={wishlist.length}
          onGoHome={resetToHome}
          onGoWishlist={() => setView("wishlist")}
          onOpenCart={() => setCartOpen(true)}
          onGoAccount={goAccount}
        />

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
          onRemove={cart.remove}
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

        {welcome.open && (
          <WelcomeOffer lang={lang} onAnswer={welcome.answer} onRemember={welcome.remember} />
        )}

        <Toast message={toast} />
      </div>
    </I18nProvider>
  );
}
