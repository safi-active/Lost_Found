import os
import hashlib
import re
import secrets
import smtplib
import webbrowser
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from pymongo.errors import DuplicateKeyError
from db import init_db, lost_claims, found_items, notifications, audit_logs, users

from auth import (
    admin_required,
    change_user_password,
    login_required,
    login_user,
    logout_user,
    register_user,
    SUPPORTED_LANGUAGE_CODES,
)

# Setup Flask with custom frontend folder paths
app = Flask(__name__, template_folder="../frontend/templates", static_folder="../frontend/static")
app.secret_key = os.getenv("SECRET_KEY", "dev_key_fallback")
SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "Français",
    "sw": "Kiswahili",
    "rw": "Kinyarwanda",
    "es": "Español",
    "de": "Deutsch",
    "zh": "中文",
    "ja": "日本語",
}
if SUPPORTED_LANGUAGES.keys() != SUPPORTED_LANGUAGE_CODES:
    raise RuntimeError("Supported language labels and authentication codes must match.")
TRANSLATIONS = {
    "Home": "Inicio",
    "About": "Acerca de",
    "Campus": "Campus",
    "Campus L&F": "Objetos perdidos",
    "Campus Lost and Found home": "Inicio de objetos perdidos del campus",
    "Campus community": "Comunidad universitaria",
    "Campus Lost & Found": "Objetos perdidos del campus",
    "Lost & Found": "Objetos perdidos y encontrados",
    "A secure, simple way for our campus community to report and recover lost belongings.": "Una forma segura y sencilla para que nuestra comunidad universitaria reporte y recupere pertenencias perdidas.",
    "Students gathered in a university classroom": "Estudiantes reunidos en un aula universitaria",
    "Students moving through a busy campus building": "Estudiantes recorriendo un edificio universitario",
    "A student browsing books in the university library": "Un estudiante buscando libros en la biblioteca universitaria",
    "Here is an overview of your lost item reports.": "Este es un resumen de tus reportes de objetos perdidos.",
    "Campus community impact": "Impacto en la comunidad universitaria",
    "Login": "Iniciar sesión",
    "Register": "Registrarse",
    "Dashboard": "Panel",
    "Register Found Item": "Registrar objeto encontrado",
    "Manage Claims": "Administrar reclamaciones",
    "Report Lost Item": "Reportar objeto perdido",
    "My Claims": "Mis reclamaciones",
    "Settings": "Configuración",
    "Language": "Idioma",
    "Save language": "Guardar idioma",
    "Logout": "Cerrar sesión",
    "Account settings": "Configuración de la cuenta",
    "Administrator settings": "Configuración del administrador",
    "Manage your account details and password.": "Administra los datos de tu cuenta y contraseña.",
    "Manage administrator account details, password, and system language.": "Administra los datos de la cuenta de administrador, la contraseña y el idioma del sistema.",
    "Full name": "Nombre completo",
    "Registered email": "Correo electrónico registrado",
    "Current password": "Contraseña actual",
    "New password": "Nueva contraseña",
    "Confirm new password": "Confirma la nueva contraseña",
    "Save account details": "Guardar datos de la cuenta",
    "Change password": "Cambiar contraseña",
    "At least 8 characters": "Al menos 8 caracteres",
    "Reset a forgotten password": "Restablecer una contraseña olvidada",
    "Send reset link": "Enviar enlace de restablecimiento",
    "Set a new password": "Establecer una nueva contraseña",
    "Password": "Contraseña",
    "Sign in to security dashboard": "Acceder al panel de seguridad",
    "Email address": "Correo electrónico",
    "Sign In": "Iniciar sesión",
    "Use your university account to continue.": "Usa tu cuenta universitaria para continuar.",
    "University email": "Correo universitario",
    "Don't have an account?": "¿No tienes una cuenta?",
    "Create an Account": "Crear una cuenta",
    "Campus security sign in": "Acceso del personal de seguridad",
    "Back to Home": "Volver al inicio",
    "Create an account": "Crear una cuenta",
    "Join your campus community and keep track of your reports.": "Únete a tu comunidad universitaria y lleva un seguimiento de tus reportes.",
    "Student ID": "Identificación estudiantil",
    "optional": "opcional",
    "Create Account": "Crear cuenta",
    "Already have an account?": "¿Ya tienes una cuenta?",
    "Sign in": "Iniciar sesión",
    "Campus security": "Seguridad del campus",
    "Administrator sign in": "Acceso de administrador",
    "Staff email": "Correo del personal",
    "Enter your password": "Escribe tu contraseña",
    "Student sign in": "Acceso estudiantil",
    "Recent Claims": "Reclamaciones recientes",
    "Item": "Objeto",
    "Status": "Estado",
    "Pending": "Pendiente",
    "Matched": "Asociado",
    "Resolved": "Resuelto",
    "Stored": "Guardado",
    "Date Lost": "Fecha de pérdida",
    "You have not reported any lost items yet.": "Aún no has reportado objetos perdidos.",
    "Claim ID": "N.º de reclamación",
    "Date Submitted": "Fecha de envío",
    "No claims found.": "No se encontraron reclamaciones.",
    "No lost-item claims have been submitted yet.": "Aún no se han enviado reclamaciones por objetos perdidos.",
    "Notifications": "Notificaciones",
    "You have no new notifications.": "No tienes notificaciones nuevas.",
    "Admin Dashboard": "Panel de administración",
    "Overview of all lost and found activities.": "Resumen de todas las actividades de objetos perdidos y encontrados.",
    "Total Lost Claims": "Total de reclamaciones",
    "Pending Claims": "Reclamaciones pendientes",
    "Total Found Items": "Total de objetos encontrados",
    "Items Currently Stored": "Objetos actualmente guardados",
    "Items Returned": "Objetos devueltos",
    "Manage Lost Claims": "Administrar objetos perdidos",
    "Review student reports, verify suggested matches, and record completed handovers.": "Revisa los reportes, verifica posibles coincidencias y registra las entregas completadas.",
    "Student": "Estudiante",
    "Item Lost": "Objeto perdido",
    "Suggested Matches & Handover": "Coincidencias y entrega",
    "Confirm match": "Confirmar coincidencia",
    "No stored items match this report yet.": "Aún no hay objetos guardados que coincidan con este reporte.",
    "I verified the claimant's identity and ownership.": "Verifiqué la identidad y propiedad del objeto.",
    "Record handover": "Registrar entrega",
    "Returned": "Devuelto",
    "No available match.": "No hay coincidencias disponibles.",
    "Report a Lost Item": "Reportar un objeto perdido",
    "Please provide the details of the item you lost.": "Proporciona los detalles del objeto que perdiste.",
    "Item Name *": "Nombre del objeto *",
    "Color *": "Color *",
    "Date Lost *": "Fecha de pérdida *",
    "Last Known Location (Optional)": "Último lugar conocido (opcional)",
    "Additional Description (Optional)": "Descripción adicional (opcional)",
    "Submit Claim": "Enviar reclamación",
    "Register Recovered Item": "Registrar objeto recuperado",
    "Log an item handed over to security.": "Registra un objeto entregado al personal de seguridad.",
    "Item Name (Required)": "Nombre del objeto (obligatorio)",
    "Color (Required)": "Color (obligatorio)",
    "Date Received (Required)": "Fecha de recepción (obligatoria)",
    "Location Found (Optional)": "Lugar donde se encontró (opcional)",
    "Description (Optional)": "Descripción (opcional)",
    "Handed Over By (Name)": "Entregado por (nombre)",
    "Handed Over By (Contact)": "Entregado por (contacto)",
    "Photograph (Optional)": "Fotografía (opcional)",
    "Register Item": "Registrar objeto",
    "A little help goes a long way": "Un poco de ayuda hace mucho",
    "Lost something on campus? Don't worry. Our platform connects students who have lost their belongings with those who have found them, making it easier to recover what matters.": "¿Perdiste algo en el campus? Nuestra plataforma conecta a quienes perdieron pertenencias con quienes las encontraron, facilitando su recuperación.",
    "Find Your Lost Item": "Encuentra tu objeto perdido",
    "Discover how it works": "Descubre cómo funciona",
    "Together, we find a way": "Juntos encontramos soluciones",
    "A more connected campus": "Un campus más conectado",
    "Campus Lost & Found is a central place to report missing belongings and reunite found items with their owners. We built it to replace scattered messages and notice boards with a clearer, more reliable process for students and campus security.": "Campus Lost & Found es un lugar central para reportar pertenencias perdidas y reunir los objetos encontrados con sus dueños. Reemplaza mensajes dispersos y tablones por un proceso más claro y confiable para estudiantes y seguridad.",
    "Students can submit a lost-item report and follow its status. Security staff register items handed in, review possible matches, and verify ownership before recording a return—helping the whole campus community get back to what matters.": "Los estudiantes pueden reportar objetos perdidos y consultar su estado. El personal de seguridad registra los objetos entregados, revisa posibles coincidencias y verifica la propiedad antes de registrar una devolución.",
    "Looking out for one another": "Cuidándonos entre todos",
    "Across every corner of campus": "En cada rincón del campus",
    "From the library to the lecture hall": "De la biblioteca al aula",
    "People we aim to help across universities": "Personas a quienes aspiramos ayudar en distintas universidades",
    "Items Reported": "Objetos reportados",
    "Items Successfully Recovered": "Objetos recuperados",
    "Items Reported — goal": "Objetos reportados — meta",
    "Items Successfully Recovered — goal": "Objetos recuperados con éxito — meta",
    "These are outreach and impact goals, not verified achievement totals.": "Estas son metas de alcance e impacto, no cifras verificadas de logros.",
    "Helping our campus community reconnect with what matters.": "Ayudamos a nuestra comunidad universitaria a recuperar lo que importa.",
    "Language preference updated.": "Se actualizó el idioma.",
    "Your current password is incorrect.": "La contraseña actual es incorrecta.",
    "Password must be at least 8 characters.": "La contraseña debe tener al menos 8 caracteres.",
    "Password updated successfully.": "La contraseña se actualizó correctamente.",
    "Name and email are required.": "El nombre y el correo son obligatorios.",
    "Enter a valid email address.": "Escribe un correo electrónico válido.",
    "That email or name is already in use.": "Ese correo o nombre ya está en uso.",
    "Account details updated successfully.": "Los datos de la cuenta se actualizaron correctamente.",
    "The new passwords do not match.": "Las nuevas contraseñas no coinciden.",
    "Password reset is not configured. Contact campus support.": "El restablecimiento de contraseñas no está configurado. Contacta al soporte del campus.",
    "If an account exists for that email, reset instructions will be emailed if delivery succeeds. Contact campus support if they don't arrive.": "Si existe una cuenta con ese correo, se enviarán instrucciones cuando el envío se complete. Contacta al soporte del campus si no las recibes.",
    "This password reset link is invalid or has expired.": "Este enlace para restablecer la contraseña no es válido o ha caducado.",
    "This password reset form expired. Open your reset link again.": "Este formulario de restablecimiento caducó. Abre nuevamente el enlace.",
    "This sign-in is restricted to campus security staff.": "Este acceso está restringido al personal de seguridad del campus.",
    "Your password was reset. Please sign in with your new password.": "Se restableció tu contraseña. Inicia sesión con la nueva contraseña.",
    "Passwords do not match.": "Las contraseñas no coinciden.",
    "Password reset failed. Please request a new link.": "No se pudo restablecer la contraseña. Solicita un enlace nuevo.",
    "Choose a supported language.": "Selecciona un idioma disponible.",
    "Invalid settings request.": "La solicitud de configuración no es válida.",
    "Your account could not be found. Please sign in again.": "No se encontró tu cuenta. Inicia sesión nuevamente.",
    "A reset link will be sent if this address is registered.": "Se enviará un enlace si esta dirección está registrada.",
    "If you don't receive an email, contact campus support.": "Si no recibes un correo, contacta al soporte del campus.",
    "Confirm password": "Confirmar contraseña",
    "Reset password": "Restablecer contraseña",
    "Account details": "Datos de la cuenta",
    "System language": "Idioma del sistema",
    "Passwords are securely hashed and cannot be displayed. Use this form or the reset link to choose a new password.": "Las contraseñas se guardan con hash seguro y no se pueden mostrar. Usa este formulario o el enlace de restablecimiento para elegir una nueva.",
    "Welcome": "Te damos la bienvenida",
    "Invalid email or password.": "El correo o la contraseña no son válidos.",
    "Email and password are required.": "El correo y la contraseña son obligatorios.",
    "Please log in to access this page.": "Inicia sesión para acceder a esta página.",
    "Administrator access required.": "Se requiere acceso de administrador.",
    "Name, email, and password are required.": "El nombre, el correo y la contraseña son obligatorios.",
    "Email or Username already exists.": "El correo o el nombre de usuario ya existen.",
    "Student ID already registered.": "La identificación estudiantil ya está registrada.",
    "Registration successful.": "El registro se completó correctamente.",
    "Successfully logged out.": "La sesión se cerró correctamente.",
    "Item name, color, and date lost are required.": "El nombre, el color y la fecha de pérdida son obligatorios.",
    "Enter a valid date lost.": "Escribe una fecha de pérdida válida.",
    "Lost item claim registered successfully!": "¡Se registró la reclamación por el objeto perdido!",
    "Item name, color, and date received are required.": "El nombre, el color y la fecha de recepción son obligatorios.",
    "Enter a valid date received.": "Escribe una fecha de recepción válida.",
    "Recovered item successfully registered.": "El objeto recuperado se registró correctamente.",
    "The selected claim or item is invalid.": "La reclamación o el objeto seleccionado no es válido.",
    "This claim or found item is no longer available for matching.": "Esta reclamación u objeto ya no está disponible para asociarse.",
    "This found item is no longer available for matching.": "Este objeto ya no está disponible para asociarse.",
    "Confirm that identity and ownership were verified before recording a handover.": "Confirma que verificaste la identidad y propiedad antes de registrar la entrega.",
    "This matched item is no longer awaiting handover.": "Este objeto asociado ya no está pendiente de entrega.",
    "The student account for this claim could not be found.": "No se encontró la cuenta estudiantil de esta reclamación.",
    "This claim has already been updated.": "Esta reclamación ya se actualizó.",
    "The item status changed before the handover could be recorded.": "El estado del objeto cambió antes de registrar la entrega.",
    "Handover recorded and item marked as returned.": "Se registró la entrega y el objeto figura como devuelto.",
    "Match confirmed. Item reserved for verification.": "Coincidencia confirmada. El objeto quedó reservado para verificación.",
}

LANGUAGE_TRANSLATIONS = {
    "fr": {
        "Home": "Accueil", "About": "À propos", "Login": "Connexion", "Register": "S’inscrire",
        "Campus Lost & Found": "Objets perdus et trouvés du campus", "Lost & Found": "Objets perdus et trouvés",
        "Campus L&F": "Objets trouvés du campus", "Campus community impact": "Impact sur la communauté universitaire",
        "A secure, simple way for our campus community to report and recover lost belongings.": "Une solution simple et sécurisée pour signaler et retrouver les objets perdus sur le campus.",
        "Lost something on campus? Don't worry. Our platform connects students who have lost their belongings with those who have found them, making it easier to recover what matters.": "Vous avez perdu quelque chose sur le campus ? Notre plateforme met en relation les personnes qui ont perdu un objet avec celles qui l'ont trouvé.",
        "Campus Lost & Found is a central place to report missing belongings and reunite found items with their owners. We built it to replace scattered messages and notice boards with a clearer, more reliable process for students and campus security.": "Campus Lost & Found centralise les signalements d'objets perdus et aide à rendre les objets trouvés à leurs propriétaires. Le service offre un processus clair et fiable aux étudiants et au personnel de sécurité.",
        "Students can submit a lost-item report and follow its status. Security staff register items handed in, review possible matches, and verify ownership before recording a return—helping the whole campus community get back to what matters.": "Les étudiants peuvent signaler un objet perdu et suivre son état. Le personnel de sécurité enregistre les objets trouvés, vérifie les correspondances et confirme leur propriété avant leur restitution.",
        "Across every corner of campus": "Dans chaque recoin du campus",
        "From the library to the lecture hall": "De la bibliothèque aux salles de cours",
        "Looking out for one another": "Veillons les uns sur les autres",
        "Helping our campus community reconnect with what matters.": "Aidons notre communauté universitaire à retrouver ce qui compte.",
        "A reset link will be sent if this address is registered.": "Un lien sera envoyé si cette adresse est associée à un compte.",
        "If you don't receive an email, contact campus support.": "Si vous ne recevez pas d’e-mail, contactez le support du campus.",
        "Dashboard": "Tableau de bord", "Manage Claims": "Gérer les réclamations",
        "Register Found Item": "Enregistrer un objet trouvé", "Report Lost Item": "Signaler un objet perdu",
        "My Claims": "Mes réclamations", "Notifications": "Notifications", "Settings": "Paramètres",
        "Language": "Langue", "Save language": "Enregistrer la langue", "Logout": "Déconnexion",
        "Account settings": "Paramètres du compte", "Administrator settings": "Paramètres administrateur",
        "Manage your account details and password.": "Gérez les informations de votre compte et votre mot de passe.",
        "Manage administrator account details, password, and system language.": "Gérez le compte administrateur, le mot de passe et la langue du système.",
        "Account details": "Informations du compte", "System language": "Langue du système",
        "Full name": "Nom complet", "Registered email": "Adresse e-mail enregistrée",
        "Email address": "Adresse e-mail", "University email": "E-mail universitaire",
        "Staff email": "E-mail du personnel", "Current password": "Mot de passe actuel",
        "New password": "Nouveau mot de passe", "Confirm new password": "Confirmer le nouveau mot de passe",
        "Confirm password": "Confirmer le mot de passe", "Password": "Mot de passe",
        "Save account details": "Enregistrer les informations", "Change password": "Modifier le mot de passe",
        "At least 8 characters": "Au moins 8 caractères", "Reset a forgotten password": "Réinitialiser un mot de passe oublié",
        "Send reset link": "Envoyer le lien de réinitialisation", "Set a new password": "Définir un nouveau mot de passe",
        "Reset password": "Réinitialiser le mot de passe", "Sign In": "Se connecter",
        "Sign in": "Se connecter", "Create an account": "Créer un compte",
        "Create an Account": "Créer un compte", "Create Account": "Créer le compte",
        "Already have an account?": "Vous avez déjà un compte ?", "Don't have an account?": "Vous n’avez pas de compte ?",
        "Back to Home": "Retour à l’accueil", "Use your university account to continue.": "Connectez-vous avec votre compte universitaire.",
        "Campus security": "Sécurité du campus", "Campus security sign in": "Connexion du personnel de sécurité",
        "Administrator sign in": "Connexion administrateur", "Student sign in": "Connexion étudiant",
        "A little help goes a long way": "Un peu d’aide peut faire beaucoup",
        "A more connected campus": "Un campus plus connecté", "Together, we find a way": "Ensemble, trouvons une solution",
        "Find Your Lost Item": "Retrouver mon objet perdu", "Discover how it works": "Découvrez comment ça marche",
        "People we aim to help across universities": "Personnes que nous souhaitons aider dans les universités",
        "Items Reported — goal": "Objets signalés — objectif",
        "Items Successfully Recovered — goal": "Objets récupérés — objectif",
        "These are outreach and impact goals, not verified achievement totals.": "Il s’agit d’objectifs, et non de résultats vérifiés.",
        "Recent Claims": "Réclamations récentes", "Item": "Objet", "Status": "Statut",
        "Date Lost": "Date de perte", "Claim ID": "N° de réclamation", "Date Submitted": "Date de soumission",
        "You have no new notifications.": "Vous n’avez pas de nouvelles notifications.",
        "You have not reported any lost items yet.": "Vous n’avez pas encore signalé d’objet perdu.",
        "No claims found.": "Aucune réclamation trouvée.", "Welcome": "Bienvenue",
    },
    "sw": {
        "Home": "Nyumbani", "About": "Kuhusu", "Login": "Ingia", "Register": "Jisajili",
        "Campus Lost & Found": "Vifaa Vilivyopotea Chuoni", "Lost & Found": "Vilivyopotea na kupatikana",
        "Campus L&F": "Vifaa vilivyopatikana chuoni", "Campus community impact": "Athari kwa jamii ya chuo",
        "A secure, simple way for our campus community to report and recover lost belongings.": "Njia rahisi na salama kwa jamii ya chuo kuripoti na kupata vitu vilivyopotea.",
        "Lost something on campus? Don't worry. Our platform connects students who have lost their belongings with those who have found them, making it easier to recover what matters.": "Umepoteza kitu chuoni? Jukwaa letu huwaunganisha waliopoteza vitu na waliovipata ili kurahisisha kuvirudisha.",
        "Campus Lost & Found is a central place to report missing belongings and reunite found items with their owners. We built it to replace scattered messages and notice boards with a clearer, more reliable process for students and campus security.": "Campus Lost & Found ni mahali pa pamoja pa kuripoti vitu vilivyopotea na kuvirudisha kwa wenyewe. Hutoa utaratibu wa wazi kwa wanafunzi na usalama wa chuo.",
        "Students can submit a lost-item report and follow its status. Security staff register items handed in, review possible matches, and verify ownership before recording a return—helping the whole campus community get back to what matters.": "Wanafunzi wanaweza kuripoti vitu vilivyopotea na kufuatilia hali yake. Usalama wa chuo husajili vitu vilivyopatikana, hukagua vinavyoweza kufanana na kuthibitisha mmiliki kabla ya kukirejesha.",
        "Across every corner of campus": "Katika kila pembe ya chuo",
        "From the library to the lecture hall": "Kutoka maktaba hadi darasani",
        "Looking out for one another": "Kujali kila mmoja",
        "Helping our campus community reconnect with what matters.": "Tunalisaidia jamii ya chuo kupata tena vitu muhimu.",
        "A reset link will be sent if this address is registered.": "Kiungo kitatumwa ikiwa anwani hii imesajiliwa.",
        "If you don't receive an email, contact campus support.": "Usipopokea barua pepe, wasiliana na usaidizi wa chuo.",
        "Dashboard": "Dashibodi", "Manage Claims": "Simamia madai",
        "Register Found Item": "Sajili kifaa kilichopatikana", "Report Lost Item": "Ripoti kifaa kilichopotea",
        "My Claims": "Madai yangu", "Notifications": "Arifa", "Settings": "Mipangilio",
        "Language": "Lugha", "Save language": "Hifadhi lugha", "Logout": "Toka",
        "Account settings": "Mipangilio ya akaunti", "Administrator settings": "Mipangilio ya msimamizi",
        "Manage your account details and password.": "Dhibiti maelezo na nenosiri la akaunti yako.",
        "Manage administrator account details, password, and system language.": "Dhibiti akaunti ya msimamizi, nenosiri na lugha ya mfumo.",
        "Account details": "Maelezo ya akaunti", "System language": "Lugha ya mfumo",
        "Full name": "Jina kamili", "Registered email": "Barua pepe iliyosajiliwa",
        "Email address": "Anwani ya barua pepe", "University email": "Barua pepe ya chuo kikuu",
        "Staff email": "Barua pepe ya mfanyakazi", "Current password": "Nenosiri la sasa",
        "New password": "Nenosiri jipya", "Confirm new password": "Thibitisha nenosiri jipya",
        "Confirm password": "Thibitisha nenosiri", "Password": "Nenosiri",
        "Save account details": "Hifadhi maelezo ya akaunti", "Change password": "Badilisha nenosiri",
        "At least 8 characters": "Angalau vibambo 8", "Reset a forgotten password": "Weka upya nenosiri lililosahaulika",
        "Send reset link": "Tuma kiungo cha kuweka upya", "Set a new password": "Weka nenosiri jipya",
        "Reset password": "Weka upya nenosiri", "Sign In": "Ingia",
        "Sign in": "Ingia", "Create an account": "Fungua akaunti",
        "Create an Account": "Fungua akaunti", "Create Account": "Fungua akaunti",
        "Already have an account?": "Tayari una akaunti?", "Don't have an account?": "Huna akaunti?",
        "Back to Home": "Rudi mwanzo", "Use your university account to continue.": "Tumia akaunti yako ya chuo kikuu kuendelea.",
        "Campus security": "Usalama wa chuo", "Campus security sign in": "Ingia kama mhudumu wa usalama",
        "Administrator sign in": "Ingia kama msimamizi", "Student sign in": "Ingia kama mwanafunzi",
        "A little help goes a long way": "Msaada mdogo una maana kubwa",
        "A more connected campus": "Chuo kilichounganishwa zaidi", "Together, we find a way": "Pamoja, tunapata suluhisho",
        "Find Your Lost Item": "Tafuta kifaa chako kilichopotea", "Discover how it works": "Jifunze jinsi inavyofanya kazi",
        "People we aim to help across universities": "Watu tunaolenga kuwasaidia katika vyuo vikuu",
        "Items Reported — goal": "Vifaa vilivyoripotiwa — lengo",
        "Items Successfully Recovered — goal": "Vifaa vilivyopatikana — lengo",
        "These are outreach and impact goals, not verified achievement totals.": "Haya ni malengo, si jumla ya mafanikio yaliyothibitishwa.",
        "Recent Claims": "Madai ya hivi karibuni", "Item": "Kifaa", "Status": "Hali",
        "Date Lost": "Tarehe kilipopotea", "Claim ID": "Nambari ya dai", "Date Submitted": "Tarehe iliyowasilishwa",
        "You have no new notifications.": "Huna arifa mpya.",
        "You have not reported any lost items yet.": "Bado hujaripoti kifaa kilichopotea.",
        "No claims found.": "Hakuna madai yaliyopatikana.", "Welcome": "Karibu",
    },
    "rw": {
        "Home": "Ahabanza", "About": "Ibyerekeye", "Login": "Injira", "Register": "Iyandikishe",
        "Campus Lost & Found": "Ibintu byabuze kuri kaminuza", "Lost & Found": "Ibintu byabuze n'ibyabonetse",
        "Campus L&F": "Ibintu byabonetse kuri kaminuza", "Campus community impact": "Ingaruka ku muryango wa kaminuza",
        "A secure, simple way for our campus community to report and recover lost belongings.": "Uburyo bworoshye kandi butekanye bwo kumenyesha no kubona ibintu byatakaye kuri kaminuza.",
        "Lost something on campus? Don't worry. Our platform connects students who have lost their belongings with those who have found them, making it easier to recover what matters.": "Wabuze ikintu kuri kaminuza? Uru rubuga ruhuza ababuze ibintu n'ababibonye kugira ngo byoroshe kubisubirana.",
        "Campus Lost & Found is a central place to report missing belongings and reunite found items with their owners. We built it to replace scattered messages and notice boards with a clearer, more reliable process for students and campus security.": "Campus Lost & Found ni ahantu hamwe ho kumenyesha ibintu byabuze no kubisubiza ba nyirabyo. Ifasha abanyeshuri n'abashinzwe umutekano gukurikirana ibyabonetse.",
        "Students can submit a lost-item report and follow its status. Security staff register items handed in, review possible matches, and verify ownership before recording a return—helping the whole campus community get back to what matters.": "Abanyeshuri bashobora kumenyesha ikintu cyabuze no gukurikirana uko kigenda. Abashinzwe umutekano bandika ibyabonetse, bakagenzura nyirabyo mbere yo kubisubiza.",
        "Across every corner of campus": "Mu mpande zose za kaminuza",
        "From the library to the lecture hall": "Kuva mu isomero kugera mu ishuri",
        "Looking out for one another": "Kwita kuri bagenzi bacu",
        "Helping our campus community reconnect with what matters.": "Dufasha umuryango wa kaminuza kongera kubona iby'ingenzi.",
        "A reset link will be sent if this address is registered.": "Umurongo wo gusubizaho uzoherezwa niba iyi imeyili yanditswe.",
        "If you don't receive an email, contact campus support.": "Nutaboneza imeyili, hamagara ubufasha bwa kaminuza.",
        "Dashboard": "Imbonerahamwe", "Manage Claims": "Genzura ibisabwa",
        "Register Found Item": "Andikisha ikintu cyabonetse", "Report Lost Item": "Menyesha ikintu cyatakaye",
        "My Claims": "Ibyo nasabye", "Notifications": "Ubutumwa", "Settings": "Amagenamiterere",
        "Language": "Ururimi", "Save language": "Bika ururimi", "Logout": "Sohoka",
        "Account settings": "Amagenamiterere ya konti", "Administrator settings": "Amagenamiterere y'umuyobozi",
        "Manage your account details and password.": "Genzura amakuru ya konti yawe n'ijambo ry'ibanga.",
        "Manage administrator account details, password, and system language.": "Genzura konti y'umuyobozi, ijambo ry'ibanga n'ururimi rwa sisitemu.",
        "Account details": "Amakuru ya konti", "System language": "Ururimi rwa sisitemu",
        "Full name": "Amazina yose", "Registered email": "Imeyili yanditswe",
        "Email address": "Aderesi ya imeyili", "University email": "Imeyili ya kaminuza",
        "Staff email": "Imeyili y'umukozi", "Current password": "Ijambo ry'ibanga rikoreshwa",
        "New password": "Ijambo ry'ibanga rishya", "Confirm new password": "Emeza ijambo ry'ibanga rishya",
        "Confirm password": "Emeza ijambo ry'ibanga", "Password": "Ijambo ry'ibanga",
        "Save account details": "Bika amakuru ya konti", "Change password": "Hindura ijambo ry'ibanga",
        "At least 8 characters": "Nibura inyuguti 8", "Reset a forgotten password": "Subizaho ijambo ry'ibanga wibagiwe",
        "Send reset link": "Ohereza umurongo wo gusubizaho", "Set a new password": "Shyiraho ijambo ry'ibanga rishya",
        "Reset password": "Subizaho ijambo ry'ibanga", "Sign In": "Injira",
        "Sign in": "Injira", "Create an account": "Fungura konti",
        "Create an Account": "Fungura konti", "Create Account": "Fungura konti",
        "Already have an account?": "Usanzwe ufite konti?", "Don't have an account?": "Nta konti ufite?",
        "Back to Home": "Subira ahabanza", "Use your university account to continue.": "Koresha konti ya kaminuza yawe ukomeze.",
        "Campus security": "Umutekano wa kaminuza", "Campus security sign in": "Injira nk'umukozi ushinzwe umutekano",
        "Administrator sign in": "Injira nk'umuyobozi", "Student sign in": "Injira nk'umunyeshuri",
        "A little help goes a long way": "Ubufasha buto bugira akamaro kanini",
        "A more connected campus": "Kaminuza ihurijwe hamwe kurushaho", "Together, we find a way": "Dufatanyije tubona igisubizo",
        "Find Your Lost Item": "Shaka ikintu cyawe cyatakaye", "Discover how it works": "Menya uko bikora",
        "People we aim to help across universities": "Abantu tugamije gufasha muri za kaminuza",
        "Items Reported — goal": "Ibintu byamenyeshejwe — intego",
        "Items Successfully Recovered — goal": "Ibintu byabonetse — intego",
        "These are outreach and impact goals, not verified achievement totals.": "Izi ni intego, si imibare y'ibyagezweho yemejwe.",
        "Recent Claims": "Ibyasabwe vuba", "Item": "Ikintu", "Status": "Imiterere",
        "Date Lost": "Itariki cyatakariyeho", "Claim ID": "Nomero y'icyasabwe", "Date Submitted": "Itariki byatangiweho",
        "You have no new notifications.": "Nta butumwa bushya ufite.",
        "You have not reported any lost items yet.": "Nta kintu cyatakaye uramenyesha.", "No claims found.": "Nta byasabwe byabonetse.",
        "Welcome": "Murakaza neza",
    },
    "de": {
        "Home": "Startseite", "About": "Über uns", "Login": "Anmelden", "Register": "Registrieren",
        "Campus Lost & Found": "Fundbüro des Campus", "Lost & Found": "Verloren und gefunden",
        "Campus L&F": "Campus-Fundbüro", "Campus community impact": "Wirkung für die Hochschulgemeinschaft",
        "A secure, simple way for our campus community to report and recover lost belongings.": "Ein sicherer, einfacher Weg, verlorene Gegenstände auf dem Campus zu melden und wiederzufinden.",
        "Lost something on campus? Don't worry. Our platform connects students who have lost their belongings with those who have found them, making it easier to recover what matters.": "Etwas auf dem Campus verloren? Unsere Plattform verbindet Personen, die etwas verloren oder gefunden haben, damit wichtige Dinge zurückgegeben werden können.",
        "Campus Lost & Found is a central place to report missing belongings and reunite found items with their owners. We built it to replace scattered messages and notice boards with a clearer, more reliable process for students and campus security.": "Campus Lost & Found bündelt Verlustmeldungen und hilft dabei, gefundene Gegenstände ihren Besitzern zurückzugeben. Der Dienst bietet Studierenden und der Campus-Sicherheit einen klaren, verlässlichen Ablauf.",
        "Students can submit a lost-item report and follow its status. Security staff register items handed in, review possible matches, and verify ownership before recording a return—helping the whole campus community get back to what matters.": "Studierende können Verluste melden und den Status verfolgen. Das Sicherheitspersonal erfasst gefundene Gegenstände, prüft mögliche Übereinstimmungen und bestätigt den Besitz vor der Rückgabe.",
        "Across every corner of campus": "Auf dem ganzen Campus",
        "From the library to the lecture hall": "Von der Bibliothek bis zum Hörsaal",
        "Looking out for one another": "Wir achten aufeinander",
        "Helping our campus community reconnect with what matters.": "Wir helfen unserer Hochschulgemeinschaft, Wichtiges wiederzufinden.",
        "A reset link will be sent if this address is registered.": "Ein Link wird gesendet, wenn diese Adresse registriert ist.",
        "If you don't receive an email, contact campus support.": "Wenn Sie keine E-Mail erhalten, wenden Sie sich an den Campus-Support.",
        "Dashboard": "Übersicht", "Manage Claims": "Verlustmeldungen verwalten",
        "Register Found Item": "Gefundenen Gegenstand erfassen", "Report Lost Item": "Verlust melden",
        "My Claims": "Meine Meldungen", "Notifications": "Benachrichtigungen", "Settings": "Einstellungen",
        "Language": "Sprache", "Save language": "Sprache speichern", "Logout": "Abmelden",
        "Account settings": "Kontoeinstellungen", "Administrator settings": "Administratoreinstellungen",
        "Manage your account details and password.": "Verwalten Sie Ihre Kontodaten und Ihr Passwort.",
        "Manage administrator account details, password, and system language.": "Verwalten Sie Administratorkonto, Passwort und Systemsprache.",
        "Account details": "Kontodaten", "System language": "Systemsprache",
        "Full name": "Vollständiger Name", "Registered email": "Registrierte E-Mail-Adresse",
        "Email address": "E-Mail-Adresse", "University email": "Hochschul-E-Mail",
        "Staff email": "Mitarbeiter-E-Mail", "Current password": "Aktuelles Passwort",
        "New password": "Neues Passwort", "Confirm new password": "Neues Passwort bestätigen",
        "Confirm password": "Passwort bestätigen", "Password": "Passwort",
        "Save account details": "Kontodaten speichern", "Change password": "Passwort ändern",
        "At least 8 characters": "Mindestens 8 Zeichen", "Reset a forgotten password": "Vergessenes Passwort zurücksetzen",
        "Send reset link": "Link zum Zurücksetzen senden", "Set a new password": "Neues Passwort festlegen",
        "Reset password": "Passwort zurücksetzen", "Sign In": "Anmelden", "Sign in": "Anmelden",
        "Create an account": "Konto erstellen", "Create an Account": "Konto erstellen", "Create Account": "Konto erstellen",
        "Already have an account?": "Sie haben bereits ein Konto?", "Don't have an account?": "Noch kein Konto?",
        "Back to Home": "Zurück zur Startseite", "Use your university account to continue.": "Melden Sie sich mit Ihrem Hochschulkonto an.",
        "Campus security": "Campussicherheit", "Campus security sign in": "Anmeldung für Sicherheitspersonal",
        "Administrator sign in": "Administrator-Anmeldung", "Student sign in": "Studenten-Anmeldung",
        "A little help goes a long way": "Kleine Hilfe mit großer Wirkung",
        "A more connected campus": "Ein besser vernetzter Campus", "Together, we find a way": "Gemeinsam finden wir eine Lösung",
        "Find Your Lost Item": "Verlorenen Gegenstand finden", "Discover how it works": "So funktioniert es",
        "People we aim to help across universities": "Menschen, denen wir an Hochschulen helfen möchten",
        "Items Reported — goal": "Gemeldete Gegenstände — Ziel",
        "Items Successfully Recovered — goal": "Erfolgreich zurückgegebene Gegenstände — Ziel",
        "These are outreach and impact goals, not verified achievement totals.": "Dies sind Ziele, keine bestätigten Erfolgszahlen.",
        "Recent Claims": "Neueste Verlustmeldungen", "Item": "Gegenstand", "Status": "Status",
        "Date Lost": "Verlustdatum", "Claim ID": "Meldungsnummer", "Date Submitted": "Eingereicht am",
        "You have no new notifications.": "Sie haben keine neuen Benachrichtigungen.",
        "You have not reported any lost items yet.": "Sie haben noch keine Gegenstände als verloren gemeldet.",
        "No claims found.": "Keine Meldungen gefunden.", "Welcome": "Willkommen",
    },
    "zh": {
        "Home": "首页", "About": "关于", "Login": "登录", "Register": "注册",
        "Campus Lost & Found": "校园失物招领", "Lost & Found": "失物招领",
        "Campus L&F": "校园失物招领", "Campus community impact": "校园社区影响",
        "A secure, simple way for our campus community to report and recover lost belongings.": "为校园社区提供安全、便捷的失物申报与找回服务。",
        "Lost something on campus? Don't worry. Our platform connects students who have lost their belongings with those who have found them, making it easier to recover what matters.": "在校园里丢了东西？别担心。本平台帮助失主与拾获者联系，让重要物品更容易物归原主。",
        "Campus Lost & Found is a central place to report missing belongings and reunite found items with their owners. We built it to replace scattered messages and notice boards with a clearer, more reliable process for students and campus security.": "校园失物招领平台集中处理失物申报，帮助拾获物品归还失主，为学生和校园安保提供清晰可靠的流程。",
        "Students can submit a lost-item report and follow its status. Security staff register items handed in, review possible matches, and verify ownership before recording a return—helping the whole campus community get back to what matters.": "学生可以提交失物申报并查看进度。安保人员登记拾获物品、核对可能的匹配，并在确认物主后记录归还。",
        "Across every corner of campus": "遍布校园各处",
        "From the library to the lecture hall": "从图书馆到教室",
        "Looking out for one another": "彼此关照",
        "Helping our campus community reconnect with what matters.": "帮助校园社区找回重要物品。",
        "A reset link will be sent if this address is registered.": "如果该邮箱已注册，我们将发送重置链接。",
        "If you don't receive an email, contact campus support.": "如果没有收到邮件，请联系校园支持服务。",
        "Dashboard": "控制面板", "Manage Claims": "管理失物申报",
        "Register Found Item": "登记拾获物品", "Report Lost Item": "报告遗失物品",
        "My Claims": "我的申报", "Notifications": "通知", "Settings": "设置",
        "Language": "语言", "Save language": "保存语言", "Logout": "退出登录",
        "Account settings": "账户设置", "Administrator settings": "管理员设置",
        "Manage your account details and password.": "管理您的账户信息和密码。",
        "Manage administrator account details, password, and system language.": "管理管理员账户信息、密码和系统语言。",
        "Account details": "账户信息", "System language": "系统语言",
        "Full name": "姓名", "Registered email": "注册邮箱", "Email address": "电子邮箱",
        "University email": "学校邮箱", "Staff email": "工作人员邮箱", "Current password": "当前密码",
        "New password": "新密码", "Confirm new password": "确认新密码", "Confirm password": "确认密码",
        "Password": "密码", "Save account details": "保存账户信息", "Change password": "修改密码",
        "At least 8 characters": "至少 8 个字符", "Reset a forgotten password": "重置忘记的密码",
        "Send reset link": "发送重置链接", "Set a new password": "设置新密码", "Reset password": "重置密码",
        "Sign In": "登录", "Sign in": "登录", "Create an account": "创建账户",
        "Create an Account": "创建账户", "Create Account": "创建账户", "Already have an account?": "已有账户？",
        "Don't have an account?": "还没有账户？", "Back to Home": "返回首页",
        "Use your university account to continue.": "使用您的学校账户继续。",
        "Campus security": "校园安保", "Campus security sign in": "安保人员登录",
        "Administrator sign in": "管理员登录", "Student sign in": "学生登录",
        "A little help goes a long way": "小小帮助，意义非凡", "A more connected campus": "联系更紧密的校园",
        "Together, we find a way": "携手寻找解决办法", "Find Your Lost Item": "寻找遗失物品",
        "Discover how it works": "了解使用方法", "People we aim to help across universities": "我们希望帮助的各校师生",
        "Items Reported — goal": "遗失物品申报目标", "Items Successfully Recovered — goal": "物品成功归还目标",
        "These are outreach and impact goals, not verified achievement totals.": "以上为服务目标，并非经核实的成果数据。",
        "Recent Claims": "最近的申报", "Item": "物品", "Status": "状态", "Date Lost": "遗失日期",
        "Claim ID": "申报编号", "Date Submitted": "提交日期", "You have no new notifications.": "您没有新通知。",
        "You have not reported any lost items yet.": "您尚未报告遗失物品。", "No claims found.": "未找到申报。",
        "Welcome": "欢迎",
    },
    "ja": {
        "Home": "ホーム", "About": "概要", "Login": "ログイン", "Register": "登録",
        "Campus Lost & Found": "キャンパス落とし物案内", "Lost & Found": "落とし物案内",
        "Campus L&F": "キャンパス落とし物案内", "Campus community impact": "キャンパスコミュニティへの貢献",
        "A secure, simple way for our campus community to report and recover lost belongings.": "キャンパスでの落とし物を安全かつ簡単に届け出て、見つけるためのサービスです。",
        "Lost something on campus? Don't worry. Our platform connects students who have lost their belongings with those who have found them, making it easier to recover what matters.": "キャンパスで何かをなくしましたか？このサービスは、落とした人と拾った人をつなぎ、大切な物を見つけやすくします。",
        "Campus Lost & Found is a central place to report missing belongings and reunite found items with their owners. We built it to replace scattered messages and notice boards with a clearer, more reliable process for students and campus security.": "キャンパス落とし物案内は、落とし物の届け出と返却をまとめて行う場所です。学生と警備スタッフが安心して利用できる明確な手続きを提供します。",
        "Students can submit a lost-item report and follow its status. Security staff register items handed in, review possible matches, and verify ownership before recording a return—helping the whole campus community get back to what matters.": "学生は落とし物を届け出て状況を確認できます。警備スタッフは拾得物を登録し、持ち主を確認してから返却を記録します。",
        "Across every corner of campus": "キャンパスのあらゆる場所で",
        "From the library to the lecture hall": "図書館から講義室まで",
        "Looking out for one another": "お互いを思いやる",
        "Helping our campus community reconnect with what matters.": "大切な物を取り戻し、キャンパスのつながりを支えます。",
        "A reset link will be sent if this address is registered.": "登録済みのアドレスにはリセットリンクを送信します。",
        "If you don't receive an email, contact campus support.": "メールが届かない場合は、キャンパスサポートにお問い合わせください。",
        "Dashboard": "ダッシュボード", "Manage Claims": "紛失届の管理",
        "Register Found Item": "拾得物を登録", "Report Lost Item": "紛失物を届け出る",
        "My Claims": "自分の届け出", "Notifications": "通知", "Settings": "設定",
        "Language": "言語", "Save language": "言語を保存", "Logout": "ログアウト",
        "Account settings": "アカウント設定", "Administrator settings": "管理者設定",
        "Manage your account details and password.": "アカウント情報とパスワードを管理します。",
        "Manage administrator account details, password, and system language.": "管理者アカウント、パスワード、システム言語を管理します。",
        "Account details": "アカウント情報", "System language": "システム言語",
        "Full name": "氏名", "Registered email": "登録済みメールアドレス", "Email address": "メールアドレス",
        "University email": "大学のメールアドレス", "Staff email": "職員のメールアドレス",
        "Current password": "現在のパスワード", "New password": "新しいパスワード",
        "Confirm new password": "新しいパスワードを確認", "Confirm password": "パスワードを確認",
        "Password": "パスワード", "Save account details": "アカウント情報を保存",
        "Change password": "パスワードを変更", "At least 8 characters": "8文字以上",
        "Reset a forgotten password": "忘れたパスワードをリセット", "Send reset link": "リセットリンクを送信",
        "Set a new password": "新しいパスワードを設定", "Reset password": "パスワードをリセット",
        "Sign In": "ログイン", "Sign in": "ログイン", "Create an account": "アカウントを作成",
        "Create an Account": "アカウントを作成", "Create Account": "アカウントを作成",
        "Already have an account?": "すでにアカウントをお持ちですか？", "Don't have an account?": "アカウントをお持ちでないですか？",
        "Back to Home": "ホームに戻る", "Use your university account to continue.": "大学アカウントで続行してください。",
        "Campus security": "キャンパス警備", "Campus security sign in": "警備スタッフログイン",
        "Administrator sign in": "管理者ログイン", "Student sign in": "学生ログイン",
        "A little help goes a long way": "小さな助けが大きな力に", "A more connected campus": "つながりのあるキャンパスへ",
        "Together, we find a way": "一緒に解決策を見つけましょう", "Find Your Lost Item": "落とし物を探す",
        "Discover how it works": "利用方法を見る", "People we aim to help across universities": "大学を越えて支援したい人々",
        "Items Reported — goal": "紛失届の目標", "Items Successfully Recovered — goal": "返却完了の目標",
        "These are outreach and impact goals, not verified achievement totals.": "これは目標であり、実績として確認された数ではありません。",
        "Recent Claims": "最近の届け出", "Item": "品物", "Status": "状況", "Date Lost": "紛失日",
        "Claim ID": "届け出番号", "Date Submitted": "申請日", "You have no new notifications.": "新しい通知はありません。",
        "You have not reported any lost items yet.": "まだ紛失物を届け出ていません。", "No claims found.": "届け出はありません。",
        "Welcome": "ようこそ",
    },
}


def translate(text):
    if session.get("language") == "es":
        translated = TRANSLATIONS.get(text)
        if translated is not None:
            return translated
        dynamic_messages = (
            (
                re.fullmatch(r"New lost claim submitted: (.+) \((.+)\)", text),
                lambda match: f"Nueva reclamación por objeto perdido: {match.group(1)} ({match.group(2)})",
            ),
            (
                re.fullmatch(
                    r"Campus security registered a found item that may match your (.+)\. Staff are reviewing it\.",
                    text,
                ),
                lambda match: f"El personal de seguridad registró un objeto que podría coincidir con tu {match.group(1)}. Está en revisión.",
            ),
            (
                re.fullmatch(
                    r"A possible match was found for your (.+)\. Please check your claim status\.",
                    text,
                ),
                lambda match: f"Se encontró una posible coincidencia para tu {match.group(1)}. Consulta el estado de tu reclamación.",
            ),
            (
                re.fullmatch(
                    r"Your (.+) was marked as returned by campus security\.",
                    text,
                ),
                lambda match: f"El personal de seguridad registró la devolución de tu {match.group(1)}.",
            ),
        )
        for match, render in dynamic_messages:
            if match:
                return render(match)
        return text
    return LANGUAGE_TRANSLATIONS.get(session.get("language"), {}).get(text, text)


@app.context_processor
def inject_language_helpers():
    return {"_": translate, "supported_languages": SUPPORTED_LANGUAGES}


def _password_reset_configuration():
    if app.secret_key == "dev_key_fallback" or len(app.secret_key) < 32:
        return None
    required = ("MAIL_SERVER", "MAIL_PORT", "MAIL_DEFAULT_SENDER", "PUBLIC_BASE_URL")
    if not all(os.getenv(key) for key in required):
        return None
    try:
        port = int(os.environ["MAIL_PORT"])
    except ValueError:
        return None
    base_url = os.environ["PUBLIC_BASE_URL"].rstrip("/")
    parsed_base_url = urlparse(base_url)
    if not 1 <= port <= 65535 or not parsed_base_url.netloc:
        return None
    if parsed_base_url.scheme != "https" and not (
        parsed_base_url.scheme == "http"
        and parsed_base_url.hostname in {"localhost", "127.0.0.1"}
    ):
        return None
    use_tls = os.getenv("MAIL_USE_TLS", "true").lower() not in {"0", "false", "no"}
    if not use_tls:
        return None
    return {
        "server": os.environ["MAIL_SERVER"],
        "port": port,
        "sender": os.environ["MAIL_DEFAULT_SENDER"],
        "base_url": base_url,
        "username": os.getenv("MAIL_USERNAME"),
        "password": os.getenv("MAIL_PASSWORD"),
    }


def _send_password_reset_email(email, reset_url, mail_config):
    message = EmailMessage()
    message["Subject"] = "Reset your Campus Lost & Found password"
    message["From"] = mail_config["sender"]
    message["To"] = email
    message.set_content(
        "A password reset was requested for your Campus Lost & Found account.\n\n"
        f"Use this one-time link within one hour:\n{reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    with smtplib.SMTP(mail_config["server"], mail_config["port"], timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        if mail_config["username"]:
            smtp.login(mail_config["username"], mail_config["password"] or "")
        smtp.send_message(message)

# Configure file uploads for found items
UPLOAD_FOLDER = os.path.abspath(os.path.join(app.static_folder, 'uploads'))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
# Initialize DB indexes on startup
with app.app_context():
    init_db()


def _normalise_match_text(value):
    return " ".join((value or "").casefold().split())


def _is_potential_match(claim, item):
    claim_name = _normalise_match_text(claim.get("item_name"))
    found_name = _normalise_match_text(item.get("item_name"))
    return (
        bool(claim_name and found_name)
        and (claim_name in found_name or found_name in claim_name)
        and _normalise_match_text(claim.get("color"))
        == _normalise_match_text(item.get("color"))
    )


# --- AUTH ROUTES ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        success, msg = login_user(email, password)
        if success:
            return redirect(url_for("admin_dashboard") if session["role"] == "admin" else url_for("dashboard"))
        flash(msg, "danger")
    return render_template("login.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        success, msg = login_user(
            request.form.get("email"),
            request.form.get("password"),
        )
        if success and session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        if success:
            logout_user()
            flash("This sign-in is restricted to campus security staff.", "danger")
        else:
            flash(msg, "danger")
    return render_template("admin_login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        student_id = request.form.get("student_id")
        success, msg = register_user(username, email, password, student_id=student_id)
        if success:
            flash(msg, "success")
            return redirect(url_for("login"))
        flash(msg, "danger")
    return render_template("register.html")

@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    if request.method != "POST":
        return redirect(url_for("index"))
    logout_user()
    flash("Successfully logged out.", "success")
    return redirect(url_for("index"))


def _settings_page(is_admin=False):
    user_id = ObjectId(session["user_id"])
    account = users.find_one({"_id": user_id})
    if not account:
        logout_user()
        flash("Your account could not be found. Please sign in again.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            username = (request.form.get("username") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            current_password = request.form.get("current_password") or ""
            if not check_password_hash(account["password"], current_password):
                flash("Your current password is incorrect.", "danger")
            elif not username or not email:
                flash("Name and email are required.", "danger")
            elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                flash("Enter a valid email address.", "danger")
            elif users.find_one({
                "_id": {"$ne": user_id},
                "$or": [
                    {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
                    {"username": username},
                ],
            }):
                flash("That email or name is already in use.", "danger")
            else:
                try:
                    users.update_one(
                        {"_id": user_id},
                        {"$set": {"username": username, "email": email}},
                    )
                except DuplicateKeyError:
                    flash("That email or name is already in use.", "danger")
                else:
                    session["username"] = username
                    flash("Account details updated successfully.", "success")
                    account = users.find_one({"_id": user_id})
        elif action == "password":
            new_password = request.form.get("new_password") or ""
            confirmation = request.form.get("confirm_password") or ""
            if new_password != confirmation:
                flash("The new passwords do not match.", "danger")
            else:
                success, message = change_user_password(
                    account,
                    request.form.get("current_password") or "",
                    new_password,
                )
                flash(message, "success" if success else "danger")
        else:
            flash("Invalid settings request.", "danger")

    return render_template(
        "settings.html",
        account=account,
        is_admin=is_admin,
    )


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if session.get("role") == "admin":
        return redirect(url_for("admin_settings"))
    return _settings_page()


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    return _settings_page(is_admin=True)


@app.route("/language", methods=["POST"])
@login_required
def change_language():
    language = request.form.get("language")
    if language not in SUPPORTED_LANGUAGES:
        flash("Choose a supported language.", "danger")
    else:
        result = users.update_one(
            {"_id": ObjectId(session["user_id"])},
            {"$set": {"language": language}},
        )
        if result.matched_count != 1:
            logout_user()
            flash("Your account could not be found. Please sign in again.", "danger")
            return redirect(url_for("login"))
        else:
            session["language"] = language
            flash("Language preference updated.", "success")

    return_to = request.form.get("return_to", "")
    if return_to.startswith("/") and not return_to.startswith("//"):
        return redirect(return_to)
    endpoint = "admin_dashboard" if session.get("role") == "admin" else "dashboard"
    return redirect(url_for(endpoint))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        mail_config = _password_reset_configuration()
        if not mail_config:
            flash("Password reset is not configured. Contact campus support.", "danger")
            return render_template("password_reset.html", mode="request")

        email = (request.form.get("email") or "").strip().lower()
        user = users.find_one({
            "email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}
        })
        if user:
            email = user["email"]
            secret = secrets.token_urlsafe(32)
            reset_token = URLSafeTimedSerializer(
                app.secret_key, salt="account-password-reset"
            ).dumps({
                "user_id": str(user["_id"]),
                "email": user["email"],
                "secret": secret,
            })
            users.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "password_reset_hash": hashlib.sha256(secret.encode()).hexdigest(),
                }},
            )
            reset_url = (
                f"{mail_config['base_url']}"
                f"{url_for('reset_password', token=reset_token)}"
            )
            try:
                _send_password_reset_email(email, reset_url, mail_config)
            except (OSError, smtplib.SMTPException, ValueError):
                users.update_one(
                    {"_id": user["_id"]},
                    {"$unset": {"password_reset_hash": ""}},
                )
                app.logger.exception("Password reset email delivery failed.")
                flash(
                    "If an account exists for that email, reset instructions will be emailed if delivery succeeds. Contact campus support if they don't arrive.",
                    "info",
                )
                return redirect(url_for("login"))

        flash(
            "If an account exists for that email, reset instructions will be emailed if delivery succeeds. Contact campus support if they don't arrive.",
            "info",
        )
        return redirect(url_for("login"))

    return render_template("password_reset.html", mode="request")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    serializer = URLSafeTimedSerializer(
        app.secret_key, salt="account-password-reset"
    )
    try:
        payload = serializer.loads(token, max_age=3600)
    except (BadSignature, SignatureExpired):
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))

    if not isinstance(payload, dict) or not all(
        isinstance(payload.get(key), str) for key in ("user_id", "email", "secret")
    ) or not ObjectId.is_valid(payload["user_id"]):
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))

    reset_hash = hashlib.sha256(payload["secret"].encode()).hexdigest()
    user = users.find_one({
        "_id": ObjectId(payload["user_id"]),
        "email": payload["email"],
        "password_reset_hash": reset_hash,
    })
    if not user:
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        supplied_csrf = request.form.get("reset_csrf", "")
        expected_csrf = session.get("password_reset_csrf", "")
        if not expected_csrf or not secrets.compare_digest(supplied_csrf, expected_csrf):
            flash("This password reset form expired. Open your reset link again.", "danger")
            return redirect(url_for("reset_password", token=token))

        new_password = request.form.get("new_password") or ""
        confirmation = request.form.get("confirm_password") or ""
        if new_password != confirmation:
            flash("Passwords do not match.", "danger")
        elif len(new_password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        else:
            result = users.update_one(
                {"_id": user["_id"], "password_reset_hash": reset_hash},
                {"$set": {"password": generate_password_hash(new_password)},
                 "$unset": {"password_reset_hash": ""}},
            )
            if result.modified_count != 1:
                flash("Password reset failed. Please request a new link.", "danger")
                return redirect(url_for("forgot_password"))
            logout_user()
            flash("Your password was reset. Please sign in with your new password.", "success")
            return redirect(url_for("login"))

    else:
        session["password_reset_csrf"] = secrets.token_urlsafe(32)
    return render_template(
        "password_reset.html",
        mode="reset",
        reset_csrf=session["password_reset_csrf"],
    )


# --- STUDENT ROUTES ---
@app.route("/dashboard")
@login_required
def dashboard():
    # Get user's recent claims (limit 5 for dashboard)
    user_claims = list(lost_claims.find({"user_id": ObjectId(session["user_id"])}).sort("created_at", -1).limit(5))
    return render_template("dashboard.html", claims=user_claims)

@app.route("/claim", methods=["GET", "POST"])
@login_required
def claim_item():
    if request.method == "POST":
        item_name = request.form.get("item_name")
        color = request.form.get("color")
        date_lost_str = request.form.get("date_lost")
        
        # 1. Validation
        if not item_name or not color or not date_lost_str:
            flash("Item name, color, and date lost are required.", "danger")
            return redirect(url_for("claim_item"))
        try:
            date_lost = datetime.strptime(date_lost_str, "%Y-%m-%d")
        except ValueError:
            flash("Enter a valid date lost.", "danger")
            return redirect(url_for("claim_item"))
        
        # 2. Auto-register the claim
        claim_doc = {
            "claim_id": f"LOST-{int(datetime.utcnow().timestamp())}",
            "user_id": ObjectId(session["user_id"]),
            "item_name": item_name,
            "color": color,
            "date_lost": date_lost,
            "location": request.form.get("location", ""),
            "description": request.form.get("description", ""),
            "status": "pending",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        lost_claims.insert_one(claim_doc)
        
        # 3. Create notification for Admin
        notifications.insert_one({
            "recipient_id": "admin", 
            "message": f"New lost claim submitted: {item_name} ({color})",
            "type": "new_claim",
            "read": False,
            "created_at": datetime.utcnow()
        })
        
        flash("Lost item claim registered successfully!", "success")
        return redirect(url_for("my_claims"))
        
    return render_template("claim_form.html")

@app.route("/my_claims")
@login_required
def my_claims():
    claims = list(lost_claims.find({"user_id": ObjectId(session["user_id"])}).sort("created_at", -1))
    return render_template("my_claim.html", claims=claims)

@app.route("/notifications")
@login_required
def view_notifications():
    recipient = session["user_id"] if session["role"] != "admin" else "admin"
    notifications.update_many(
        {"recipient_id": recipient, "read": False},
        {"$set": {"read": True}},
    )
    notifs = list(notifications.find({"recipient_id": recipient}).sort("created_at", -1))
    return render_template("notifications.html", notifications=notifs)

# --- ADMIN ROUTES ---
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    # Efficient MongoDB Aggregations for Stats
    stats = {
        "total_claims": lost_claims.count_documents({}),
        "total_found": found_items.count_documents({}),
        "pending_claims": lost_claims.count_documents({"status": "pending"}),
        "stored_items": found_items.count_documents({"status": "stored"}),
        "returned_items": found_items.count_documents({"status": "returned"})
    }
    return render_template("admin_dashboard.html", stats=stats)

@app.route("/admin/found", methods=["GET", "POST"])
@admin_required
def admin_found():
    if request.method == "POST":
        item_name = request.form.get("item_name")
        color = request.form.get("color")
        date_received_str = request.form.get("date_received")
        
        if not item_name or not color or not date_received_str:
            flash("Item name, color, and date received are required.", "danger")
            return redirect(url_for("admin_found"))
        try:
            date_received = datetime.strptime(date_received_str, "%Y-%m-%d")
        except ValueError:
            flash("Enter a valid date received.", "danger")
            return redirect(url_for("admin_found"))
        
        # Handle Photo Upload
        photo_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_path = f"uploads/{filename}"
                
        found_doc = {
            "recovered_id": f"FOUND-{int(datetime.utcnow().timestamp())}",
            "item_name": item_name,
            "color": color,
            "date_received": date_received,
            "location_found": request.form.get("location_found", ""),
            "description": request.form.get("description", ""),
            "handover_name": request.form.get("handover_name", ""),
            "handover_contact": request.form.get("handover_contact", ""),
            "photo_path": photo_path,
            "registered_by": ObjectId(session["user_id"]),
            "status": "stored",
            "created_at": datetime.utcnow()
        }
        inserted_item = found_items.insert_one(found_doc)

        for claim in lost_claims.find({"status": "pending"}):
            if _is_potential_match(claim, found_doc):
                notifications.insert_one({
                    "recipient_id": str(claim["user_id"]),
                    "message": f"Campus security registered a found item that may match your {claim['item_name']}. Staff are reviewing it.",
                    "type": "possible_match",
                    "found_item_id": inserted_item.inserted_id,
                    "read": False,
                    "created_at": datetime.utcnow(),
                })

        # Log action
        audit_logs.insert_one({
            "admin_id": ObjectId(session["user_id"]),
            "action": "REGISTER_FOUND_ITEM",
            "target": item_name,
            "created_at": datetime.utcnow()
        })
        
        flash("Recovered item successfully registered.", "success")
        return redirect(url_for("admin_dashboard"))
        
    return render_template("admin_found_form.html")

@app.route("/admin/claims")
@admin_required
def admin_claims():
    claims = list(lost_claims.find().sort("created_at", -1))
    found_items_list = list(found_items.find({"status": "stored"}))
    
    for claim in claims:
        claim['suggested_matches'] = []
        student = users.find_one({"_id": claim["user_id"]}, {"username": 1, "student_id": 1})
        claim["student_username"] = student.get("username", "Student") if student else "Student"
        claim["student_id"] = student.get("student_id", "") if student else ""
        for item in found_items_list:
            if claim["status"] == "pending" and _is_potential_match(claim, item):
                claim['suggested_matches'].append(item)
        if claim.get("matched_found_id"):
            claim["matched_item"] = found_items.find_one(
                {"_id": claim["matched_found_id"]}
            )
                
    return render_template("admin_claims.html", claims=claims)

@app.route("/admin/match/<claim_id>/<found_id>", methods=["POST"])
@admin_required
def confirm_match(claim_id, found_id):
    if not ObjectId.is_valid(claim_id) or not ObjectId.is_valid(found_id):
        flash("The selected claim or item is invalid.", "danger")
        return redirect(url_for("admin_claims"))

    claim_object_id = ObjectId(claim_id)
    found_object_id = ObjectId(found_id)
    claim = lost_claims.find_one({"_id": claim_object_id, "status": "pending"})
    found = found_items.find_one({"_id": found_object_id, "status": "stored"})
    if not claim or not found:
        flash("This claim or found item is no longer available for matching.", "warning")
        return redirect(url_for("admin_claims"))

    claim_result = lost_claims.update_one(
        {"_id": claim_object_id, "status": "pending"},
        {"$set": {
            "status": "matched",
            "matched_found_id": found_object_id,
            "updated_at": datetime.utcnow(),
        }},
    )
    if claim_result.modified_count != 1:
        flash("This claim has already been updated.", "warning")
        return redirect(url_for("admin_claims"))

    found_result = found_items.update_one(
        {"_id": found_object_id, "status": "stored"},
        {"$set": {"status": "reserved_for_verification"}},
    )
    if found_result.modified_count != 1:
        lost_claims.update_one(
            {"_id": claim_object_id, "status": "matched", "matched_found_id": found_object_id},
            {"$set": {"status": "pending"}, "$unset": {"matched_found_id": ""}},
        )
        flash("This found item is no longer available for matching.", "warning")
        return redirect(url_for("admin_claims"))

    notifications.insert_one({
        "recipient_id": str(claim["user_id"]),
        "message": f"A possible match was found for your {claim['item_name']}. Please check your claim status.",
        "type": "possible_match",
        "read": False,
        "created_at": datetime.utcnow(),
    })
    flash("Match confirmed. Item reserved for verification.", "success")
    return redirect(url_for("admin_claims"))


@app.route("/admin/return/<claim_id>/<found_id>", methods=["POST"])
@admin_required
def return_item(claim_id, found_id):
    if request.form.get("ownership_verified") != "yes":
        flash("Confirm that identity and ownership were verified before recording a handover.", "warning")
        return redirect(url_for("admin_claims"))
    if not ObjectId.is_valid(claim_id) or not ObjectId.is_valid(found_id):
        flash("The selected claim or item is invalid.", "danger")
        return redirect(url_for("admin_claims"))

    claim_object_id = ObjectId(claim_id)
    found_object_id = ObjectId(found_id)
    claim = lost_claims.find_one({
        "_id": claim_object_id,
        "status": "matched",
        "matched_found_id": found_object_id,
    })
    found = found_items.find_one({
        "_id": found_object_id,
        "status": "reserved_for_verification",
    })
    if not claim or not found:
        flash("This matched item is no longer awaiting handover.", "warning")
        return redirect(url_for("admin_claims"))

    student = users.find_one({"_id": claim["user_id"]}, {"username": 1})
    if not student:
        flash("The student account for this claim could not be found.", "danger")
        return redirect(url_for("admin_claims"))

    returned_at = datetime.utcnow()
    claim_result = lost_claims.update_one(
        {"_id": claim_object_id, "status": "matched", "matched_found_id": found_object_id},
        {"$set": {
            "status": "resolved",
            "returned_at": returned_at,
            "updated_at": returned_at,
        }},
    )
    if claim_result.modified_count != 1:
        flash("This claim has already been updated.", "warning")
        return redirect(url_for("admin_claims"))

    found_result = found_items.update_one(
        {"_id": found_object_id, "status": "reserved_for_verification"},
        {"$set": {
            "status": "returned",
            "returned_to_id": claim["user_id"],
            "returned_to_username": student["username"],
            "returned_by": ObjectId(session["user_id"]),
            "returned_at": returned_at,
        }},
    )
    if found_result.modified_count != 1:
        lost_claims.update_one(
            {"_id": claim_object_id, "status": "resolved"},
            {"$set": {"status": "matched"}, "$unset": {"returned_at": ""}},
        )
        flash("The item status changed before the handover could be recorded.", "warning")
        return redirect(url_for("admin_claims"))

    audit_logs.insert_one({
        "admin_id": ObjectId(session["user_id"]),
        "action": "RETURN_FOUND_ITEM",
        "target": found["item_name"],
        "student_id": claim["user_id"],
        "created_at": returned_at,
    })
    notifications.insert_one({
        "recipient_id": str(claim["user_id"]),
        "message": f"Your {claim['item_name']} was marked as returned by campus security.",
        "type": "item_returned",
        "read": False,
        "created_at": returned_at,
    })
    flash("Handover recorded and item marked as returned.", "success")
    return redirect(url_for("admin_claims"))

if __name__ == "__main__":
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True)