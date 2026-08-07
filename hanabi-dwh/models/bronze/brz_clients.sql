-- Comptes clients, tels qu'ecrits par l'application.
--
-- Les colonnes sont enumerees plutot que reprises par `select *`. C'est plus
-- long a ecrire, mais une colonne ajoutee a `users` ne se propage plus
-- silencieusement dans les trois couches : il faut passer ici, donc decider si
-- elle a sa place dans l'entrepot.
--
-- `password_hash` est absent, et c'est le point de cette enumeration : un
-- condensat de mot de passe n'a aucun usage analytique et n'a donc rien a faire
-- dans un schema que le back-office peut interroger.
select
    id,
    name,
    email,
    civility,
    birthdate,
    phone,
    addr,
    addr_extra,
    cp,
    city,
    is_admin,
    created_at
from {{ source('hanabi_oltp', 'users') }}
