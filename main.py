from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from datetime import datetime
import pytz

app = FastAPI()

# Configurazione Database SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./scuole.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Template HTML
templates = Jinja2Templates(directory="templates")
templates.env.cache = None

# Costante Master Developer
SUPER_DEV_PASSWORD = "ZSInformaticaMaster2026!"

# --- MODELLI DATABASE ---
class Scuola(Base):
    __tablename__ = "scuole"
    id = Column(Integer, primary_key=True, index=True)
    nome_scuola = Column(String, index=True)
    codice_meccanografico = Column(String, unique=True, index=True)
    password_segreteria = Column(String, default="segreteria123")
    avviso_globale = Column(Text, nullable=True)

    classi = relationship("Classe", back_populates="scuola", cascade="all, delete")
    colloqui = relationship("Colloquio", back_populates="scuola", cascade="all, delete")

class Classe(Base):
    __tablename__ = "classi"
    id = Column(Integer, primary_key=True, index=True)
    scuola_id = Column(Integer, ForeignKey("scuole.id"))
    nome_classe = Column(String, index=True)

    scuola = relationship("Scuola", back_populates="classi")
    orari = relationship("Orario", back_populates="classe", cascade="all, delete")
    variazioni = relationship("Variazione", back_populates="classe", cascade="all, delete")

class Orario(Base):
    __tablename__ = "orari"
    id = Column(Integer, primary_key=True, index=True)
    classe_id = Column(Integer, ForeignKey("classi.id"))
    giorno = Column(String)
    ora = Column(String)
    materia = Column(String)
    docente = Column(String)
    docente_sostegno = Column(String, nullable=True)
    aula = Column(String, nullable=True)

    classe = relationship("Classe", back_populates="orari")

class Variazione(Base):
    __tablename__ = "variazioni"
    id = Column(Integer, primary_key=True, index=True)
    classe_id = Column(Integer, ForeignKey("classi.id"))
    data_variazione = Column(String)
    ora_lezione = Column(String)
    tipo_variazione = Column(String)
    descrizione = Column(Text, nullable=True)

    classe = relationship("Classe", back_populates="variazioni")

class Colloquio(Base):
    __tablename__ = "colloqui"
    id = Column(Integer, primary_key=True, index=True)
    scuola_id = Column(Integer, ForeignKey("scuole.id"))
    nome_professore = Column(String)
    giorno = Column(String)
    ora_colloquio = Column(String)
    aula_ricevimento = Column(String, nullable=True)

    scuola = relationship("Scuola", back_populates="colloqui")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verifica_accesso(scuola_id: int, request: Request, db: Session):
    cookie_name = f"auth_scuola_{scuola_id}"
    auth_cookie = request.cookies.get(cookie_name)
    if auth_cookie == "autenticato":
        return True
    return False

# --- ROTTE PRINCIPALI ---

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    scuole = db.query(Scuola).all()
    errore = request.query_params.get("errore")
    return templates.TemplateResponse(request, "index.html", {"scuole": scuole, "errore": errore})

@app.post("/aggiungi-scuola")
def aggiungi_scuola(
    super_password: str = Form(...),
    nome_scuola: str = Form(...),
    codice_meccanografico: str = Form(...),
    password_segreteria: str = Form(...),
    db: Session = Depends(get_db)
):
    if super_password != SUPER_DEV_PASSWORD:
        return RedirectResponse(url="/?errore=superuser", status_code=303)
    
    nuova_scuola = Scuola(
        nome_scuola=nome_scuola,
        codice_meccanografico=codice_meccanografico.upper(),
        password_segreteria=password_segreteria
    )
    db.add(nuova_scuola)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/elimina-scuola/{scuola_id}")
def elimina_scuola(
    scuola_id: int,
    super_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if super_password != SUPER_DEV_PASSWORD:
        return RedirectResponse(url="/?errore=superuser_elimina", status_code=303)
    
    scuola = db.query(Scuola).filter(Scuola.id == scuola_id).first()
    if scuola:
        db.delete(scuola)
        db.commit()
        
    return RedirectResponse(url="/", status_code=303)

@app.get("/login/{scuola_id}", response_class=HTMLResponse)
def login_page(scuola_id: int, request: Request, db: Session = Depends(get_db)):
    scuola = db.query(Scuola).filter(Scuola.id == scuola_id).first()
    if not scuola:
        raise HTTPException(status_code=404, detail="Scuola non trovata")
    errore = request.query_params.get("errore")
    return templates.TemplateResponse(request, "login.html", {"scuola": scuola, "errore": errore})

@app.post("/login/{scuola_id}")
def login_action(scuola_id: int, password: str = Form(...), db: Session = Depends(get_db)):
    scuola = db.query(Scuola).filter(Scuola.id == scuola_id).first()
    if not scuola or scuola.password_segreteria != password:
        return RedirectResponse(url=f"/login/{scuola_id}?errore=1", status_code=303)
    
    response = RedirectResponse(url=f"/pannello/{scuola_id}", status_code=303)
    response.set_cookie(key=f"auth_scuola_{scuola_id}", value="autenticato", httponly=True)
    return response

@app.get("/logout/{scuola_id}")
def logout(scuola_id: int):
    response = RedirectResponse(url=f"/login/{scuola_id}", status_code=303)
    response.delete_cookie(key=f"auth_scuola_{scuola_id}")
    return response

@app.get("/pannello/{scuola_id}", response_class=HTMLResponse)
def pannello_segreteria(scuola_id: int, request: Request, db: Session = Depends(get_db)):
    if not verifica_accesso(scuola_id, request, db):
        return RedirectResponse(url=f"/login/{scuola_id}", status_code=303)
    
    scuola = db.query(Scuola).filter(Scuola.id == scuola_id).first()
    if not scuola:
        raise HTTPException(status_code=404, detail="Scuola non trovata")
    return templates.TemplateResponse(request, "pannello.html", {"scuola": scuola})

@app.get("/monitor/{scuola_id}", response_class=HTMLResponse)
def monitor_tv(scuola_id: int, request: Request, db: Session = Depends(get_db)):
    scuola = db.query(Scuola).filter(Scuola.id == scuola_id).first()
    if not scuola:
        raise HTTPException(status_code=404, detail="Scuola non trovata")
    
    tz_italy = pytz.timezone('Europe/Rome')
    now = datetime.now(tz_italy)
    giorni_map = {0: "Lunedì", 1: "Martedì", 2: "Mercoledì", 3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"}
    giorno_corrente = giorni_map.get(now.weekday(), "Lunedì")
    data_oggi = now.strftime('%Y-%m-%d')
    
    # Recupera i colloqui programmati per il giorno corrente
    colloqui_oggi = db.query(Colloquio).filter(
        Colloquio.scuola_id == scuola_id,
        Colloquio.giorno == giorno_corrente
    ).all()
    
    # Calcolo dinamico dell'ora corrente in base all'orario scolastico
    ora_num = now.hour
    if ora_num <= 8:
        ora_corrente = "1^ Ora"
    elif ora_num == 9:
        ora_corrente = "2^ Ora"
    elif ora_num == 10:
        ora_corrente = "3^ Ora"
    elif ora_num == 11:
        ora_corrente = "4^ Ora"
    elif ora_num == 12:
        ora_corrente = "5^ Ora"
    else:
        ora_corrente = "6^ Ora"
    
    return templates.TemplateResponse(request, "monitor.html", {
        "scuola": scuola,
        "giorno_corrente": giorno_corrente,
        "ora_corrente": ora_corrente,
        "data_oggi": data_oggi,
        "colloqui_oggi": colloqui_oggi
    })

# --- GESTIONE AZIONI PANNELLO (POST) ---

@app.post("/imposta-avviso/{scuola_id}")
def imposta_avviso(scuola_id: int, request: Request, avviso_globale: str = Form(...), db: Session = Depends(get_db)):
    if not verifica_accesso(scuola_id, request, db):
        return RedirectResponse(url=f"/login/{scuola_id}", status_code=303)
    scuola = db.query(Scuola).filter(Scuola.id == scuola_id).first()
    if scuola:
        scuola.avviso_globale = avviso_globale
        db.commit()
    return RedirectResponse(url=f"/pannello/{scuola_id}?successo=avviso", status_code=303)

@app.post("/aggiungi-classe/{scuola_id}")
def aggiungi_classe(scuola_id: int, request: Request, nome_classe: str = Form(...), db: Session = Depends(get_db)):
    if not verifica_accesso(scuola_id, request, db):
        return RedirectResponse(url=f"/login/{scuola_id}", status_code=303)
    nuova_classe = Classe(scuola_id=scuola_id, nome_classe=nome_classe)
    db.add(nuova_classe)
    db.commit()
    return RedirectResponse(url=f"/pannello/{scuola_id}?successo=classe", status_code=303)

@app.post("/aggiungi-orario/{scuola_id}")
def aggiungi_orario(
    scuola_id: int,
    request: Request,
    classe_id: int = Form(...),
    giorno: str = Form(...),
    ora: str = Form(...),
    materia: str = Form(...),
    docente: str = Form(...),
    docente_sostegno: str = Form(None),
    aula: str = Form(None),
    db: Session = Depends(get_db)
):
    if not verifica_accesso(scuola_id, request, db):
        return RedirectResponse(url=f"/login/{scuola_id}", status_code=303)
    nuovo_orario = Orario(
        classe_id=classe_id, giorno=giorno, ora=ora,
        materia=materia, docente=docente, docente_sostegno=docente_sostegno, aula=aula
    )
    db.add(nuovo_orario)
    db.commit()
    return RedirectResponse(url=f"/pannello/{scuola_id}?successo=orario", status_code=303)

@app.post("/aggiungi-variazione/{scuola_id}")
def aggiungi_variazione(
    scuola_id: int,
    request: Request,
    classe_id: int = Form(...),
    data_variazione: str = Form(...),
    ora_lezione: str = Form(...),
    tipo_variazione: str = Form(...),
    descrizione: str = Form(None),
    db: Session = Depends(get_db)
):
    if not verifica_accesso(scuola_id, request, db):
        return RedirectResponse(url=f"/login/{scuola_id}", status_code=303)
    nuova_variazione = Variazione(
        classe_id=classe_id, data_variazione=data_variazione,
        ora_lezione=ora_lezione, tipo_variazione=tipo_variazione, descrizione=descrizione
    )
    db.add(nuova_variazione)
    db.commit()
    return RedirectResponse(url=f"/pannello/{scuola_id}?successo=variazione", status_code=303)

@app.post("/aggiungi-colloquio/{scuola_id}")
def aggiungi_colloquio(
    scuola_id: int,
    request: Request,
    nome_professore: str = Form(...),
    giorno: str = Form(...),
    ora_colloquio: str = Form(...),
    aula_ricevimento: str = Form(None),
    db: Session = Depends(get_db)
):
    if not verifica_accesso(scuola_id, request, db):
        return RedirectResponse(url=f"/login/{scuola_id}", status_code=303)
    nuovo_colloquio = Colloquio(
        scuola_id=scuola_id, nome_professore=nome_professore,
        giorno=giorno, ora_colloquio=ora_colloquio, aula_ricevimento=aula_ricevimento
    )
    db.add(nuovo_colloquio)
    db.commit()
    return RedirectResponse(url=f"/pannello/{scuola_id}?successo=colloquio", status_code=303)

@app.post("/modifica-password/{scuola_id}")
def modifica_password(
    scuola_id: int,
    request: Request,
    nuova_password: str = Form(...),
    db: Session = Depends(get_db)
):
    if not verifica_accesso(scuola_id, request, db):
        return RedirectResponse(url=f"/login/{scuola_id}", status_code=303)
    scuola = db.query(Scuola).filter(Scuola.id == scuola_id).first()
    if scuola:
        scuola.password_segreteria = nuova_password
        db.commit()
    return RedirectResponse(url=f"/pannello/{scuola_id}?successo=password", status_code=303)