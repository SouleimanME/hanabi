import { useState, useEffect, useCallback } from "react";
import { Auth, Orders, setToken, getToken } from "../lib/api.js";

/**
 * Session utilisateur et historique de commandes.
 *
 * Les fonctions `login` / `signup` suivent la meme convention que le reste du
 * projet : elles renvoient `null` en cas de succes, ou le message d'erreur a
 * afficher. Cela evite d'avoir a envelopper chaque appel dans un try/catch
 * cote composant.
 */
export function useAuth() {
  const [user, setUser] = useState(null);
  const [orders, setOrders] = useState([]);

  const refreshOrders = useCallback(async () => {
    try {
      setOrders(await Orders.history());
    } catch {
      /* historique indisponible : on garde la liste precedente */
    }
  }, []);

  // Restaure la session au chargement. Un jeton expire est purge pour ne pas
  // laisser l'interface en etat "connecte" alors que l'API refuse tout.
  useEffect(() => {
    if (!getToken()) return;
    (async () => {
      try {
        setUser(await Auth.me());
        await refreshOrders();
      } catch {
        setToken(null);
      }
    })();
  }, [refreshOrders]);

  const applySession = useCallback(
    (response) => {
      setToken(response.access_token);
      setUser(response.user);
      refreshOrders();
      return response.user;
    },
    [refreshOrders],
  );

  const login = useCallback(
    async ({ email, password, antibot }) => {
      try {
        return { user: applySession(await Auth.login(email, password, antibot)), error: null };
      } catch (e) {
        return { user: null, error: e.message };
      }
    },
    [applySession],
  );

  const signup = useCallback(
    async (payload) => {
      try {
        return { user: applySession(await Auth.register(payload)), error: null };
      } catch (e) {
        return { user: null, error: e.message };
      }
    },
    [applySession],
  );

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setOrders([]);
  }, []);

  /** Relit le profil depuis l'API, sans toucher au jeton.
   *
   * Sert apres une confirmation d'adresse : le drapeau `email_verified` a
   * change cote serveur, et l'interface doit cesser de proposer un lien deja
   * suivi. Recharger la page entiere pour un booleen serait disproportionne.
   */
  const refreshUser = useCallback(async () => {
    if (!getToken()) return;
    try {
      setUser(await Auth.me());
    } catch {
      /* profil indisponible : on garde celui qu'on a */
    }
  }, []);

  /** Adopte la session rendue par une route qui authentifie d'elle-meme.
   *
   * La reinitialisation de mot de passe renvoie un jeton d'acces : la personne
   * vient de prouver son identite et de choisir un mot de passe, la renvoyer
   * vers l'ecran de connexion serait une etape de trop.
   */
  const adopterSession = useCallback((response) => applySession(response), [applySession]);

  /** Remplace le profil en memoire par celui que le serveur vient de rendre.
   *
   * Les routes de modification renvoient le profil a jour : le relire aussitot
   * par `/auth/me` serait un aller-retour pour une information qu'on tient
   * deja, et laisserait l'ecran afficher l'ancienne valeur entre les deux.
   */
  const poserProfil = useCallback((profil) => setUser(profil), []);

  return {
    user,
    orders,
    login,
    signup,
    logout,
    refreshOrders,
    refreshUser,
    adopterSession,
    poserProfil,
  };
}
