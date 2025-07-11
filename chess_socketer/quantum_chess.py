import os, shutil, random, copy, threading, time, sys, tkinter as tk
from tkinter import messagebox, simpledialog
import chess, chess.engine
import lan_socket

# ── Stockfish path ──
STOCKFISH_PATH = "stockfish.exe"   #path goes here, change if needed
if not (shutil.which(STOCKFISH_PATH) or os.path.isfile(STOCKFISH_PATH)):
    messagebox.showwarning(
        "Stockfish not found",
        "No Stockfish engine found; AI will move randomly."
    )
    STOCKFISH_PATH = None

# ── UI constants ──
S = 64  # square size
UNICODE = {
    "white": dict(zip("KQRBNP", "♔♕♖♗♘♙")),
    "black": dict(zip("KQRBNP", "♚♛♜♝♞♟")),
}
FILES = "abcdefgh"

# ── Piece ──
class Piece:
    def __init__(self, kind, color):
        self.kind, self.color = kind, color
        self.moved = False
        self.q_id  = None
    def char(self): return UNICODE[self.color][self.kind]

# ── Board ──
class Board:
    def __init__(self):
        self.branches = [self._start()]
        self.turn = "white"
        self._q_next = 1
    @staticmethod
    def _start():
        g=[[None]*8 for _ in range(8)]
        back="RNBQKBNR"
        for c,k in enumerate(back):
            g[7][c]=Piece(k,"white"); g[0][c]=Piece(k,"black")
            g[6][c]=Piece("P","white"); g[1][c]=Piece("P","black")
        return g

    # helpers
    def inside(self,r,c): return 0<=r<8 and 0<=c<8
    def piece_any(self,r,c): return next((b[r][c] for b in self.branches if b[r][c]),None)
    def merged(self,r,c):
        first=self.branches[0][r][c]
        for b in self.branches[1:]:
            if (b[r][c] is None)!=(first is None): return None
            if b[r][c] and (b[r][c].kind!=first.kind or b[r][c].color!=first.color):
                return None
        return first

    # path check
    def _pattern_ok(self,g,p,sr,sc,tr,tc):
        if not self.inside(tr,tc) or (g[tr][tc] and g[tr][tc].color==p.color): return False
        if p.kind=="K": return max(abs(sr-tr),abs(sc-tc))==1
        if p.kind=="N": return (abs(sr-tr),abs(sc-tc)) in [(2,1),(1,2)]
        if p.kind=="B":
            if abs(sr-tr)!=abs(sc-tc): return False
            dr=1 if tr>sr else -1; dc=1 if tc>sc else -1
            r,c=sr+dr,sc+dc
            while (r,c)!=(tr,tc):
                if g[r][c]: return False
                r+=dr; c+=dc
            return True
        if p.kind=="R":
            if sr!=tr and sc!=tc: return False
            if sr==tr:
                step=1 if tc>sc else -1
                for c in range(sc+step,tc,step):
                    if g[sr][c]: return False
            else:
                step=1 if tr>sr else -1
                for r in range(sr+step,tr,step):
                    if g[r][sc]: return False
            return True
        if p.kind=="Q":
            return self._pattern_ok(g,Piece("B",p.color),sr,sc,tr,tc) or \
                   self._pattern_ok(g,Piece("R",p.color),sr,sc,tr,tc)
        if p.kind=="P":
            d=-1 if p.color=="white" else 1
            start=6 if p.color=="white" else 1
            if tc==sc and g[tr][tc] is None:
                if tr-sr==d: return True
                if sr==start and tr-sr==2*d and g[sr+d][sc] is None: return True
            if abs(tc-sc)==1 and tr-sr==d and g[tr][tc] and g[tr][tc].color!=p.color:
                return True
        return False

    def _king_safe(self,g,color):
        kr=kc=None
        for r in range(8):
            for c in range(8):
                q=g[r][c]
                if q and q.kind=="K" and q.color==color: kr,kc=r,c
        opp="black" if color=="white" else "white"
        for r in range(8):
            for c in range(8):
                q=g[r][c]
                if q and q.color==opp and self._pattern_ok(g,q,r,c,kr,kc):
                    return False
        return True

    def _legal(self,g,p,sr,sc,tr,tc):
        if not self._pattern_ok(g,p,sr,sc,tr,tc): return False
        sim=copy.deepcopy(g); sim[tr][tc],sim[sr][sc]=sim[sr][sc],None
        return self._king_safe(sim,p.color)

    # moves
    def classical(self,sr,sc,tr,tc):
        nb=[]
        for g in self.branches:
            p=g[sr][sc]
            if p and self._legal(g,p,sr,sc,tr,tc):
                g2=copy.deepcopy(g); g2[tr][tc]=g2[sr][sc]; g2[sr][sc]=None; nb.append(g2)
            else: nb.append(copy.deepcopy(g))
        self.branches=nb; self.turn="black" if self.turn=="white" else "white"

    def quantum(self,sr,sc,t1r,t1c,t2r,t2c):
        surv=[g for g in self.branches if g[sr][sc]]
        if not surv: return
        tag=self._q_next; self._q_next+=1; new=[]
        for g in surv:
            p=g[sr][sc]
            if p.kind=="K": continue
            if self._legal(g,p,sr,sc,t1r,t1c):
                g1=copy.deepcopy(g); g1[t1r][t1c]=g1[sr][sc]; g1[sr][sc]=None; g1[t1r][t1c].q_id=tag; new.append(g1)
            if self._legal(g,p,sr,sc,t2r,t2c):
                g2=copy.deepcopy(g); g2[t2r][t2c]=g2[sr][sc]; g2[sr][sc]=None; g2[t2r][t2c].q_id=tag; new.append(g2)
        if new: self.branches=new; self.turn="black" if self.turn=="white" else "white"

    def collapse_on(self,r,c,seed):
        branches=[b for b in self.branches if b[r][c]]
        if not branches: return False
        self.branches=[copy.deepcopy(random.Random(seed).choice(branches))]
        for rr in range(8):
            for cc in range(8):
                p=self.branches[0][rr][cc]
                if p: p.q_id=None
        return True

    # evaluation (restored)
    def _to_board(self,color):
        g=self.branches[0]
        kmap=dict(zip("KQRBNP",(chess.KING,chess.QUEEN,chess.ROOK,chess.BISHOP,chess.KNIGHT,chess.PAWN)))
        b=chess.Board(None)
        for r in range(8):
            for c in range(8):
                p=g[r][c]
                if p:
                    b.set_piece_at(chess.square(c,7-r),
                                   chess.Piece(kmap[p.kind],p.color=="white"))
        b.turn=(color=="white")
        return b

    def evaluate(self,color,samples=4,depth=12):
        if STOCKFISH_PATH is None: return random.uniform(-50,50)
        try:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as eng:
                tot=0
                for _ in range(samples):
                    tmp=copy.deepcopy(self)
                    for r in range(8):
                        for c in range(8):
                            if any(b[r][c] and b[r][c].q_id for b in tmp.branches):
                                tmp.collapse_on(r,c,random.randrange(2**32))
                    score=eng.analyse(tmp._to_board(color), chess.engine.Limit(depth=depth))["score"].white()
                    tot+=score.score(mate_score=100000)
                return tot/samples
        except chess.engine.EngineError:
            return random.uniform(-50,50)

    # Stockfish best move for classical positions
    def engine_move(self,color,depth=15):
        if STOCKFISH_PATH is None: return None
        if len(self.branches)!=1 or any(p and p.q_id for p in sum(self.branches[0],[])): return None
        try:
            with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as eng:
                res=eng.play(self._to_board(color), chess.engine.Limit(depth=depth))
                if res.move is None: return None
                sr,sc=7-res.move.from_square//8, chess.square_file(res.move.from_square)
                tr,tc=7-res.move.to_square//8,   chess.square_file(res.move.to_square)
                return ("C",sr,sc,tr,tc)
        except chess.engine.EngineError:
            return None

    # stronger AI
    def best_ai_move(self,color,max_q=20):
        # classical use engine directly if possible
        m=self.engine_move(color,15)
        if m: return m

        best_score=-1e9 if color=="white" else 1e9
        best=None
        # classical enumeration
        for r in range(8):
            for c in range(8):
                p=self.piece_any(r,c)
                if p and p.color==color:
                    for tr in range(8):
                        for tc in range(8):
                            if self._legal(self.branches[0],p,r,c,tr,tc):
                                sim=copy.deepcopy(self); sim.classical(r,c,tr,tc)
                                sc=sim.evaluate(color,4,12)
                                if (color=="white" and sc>best_score) or (color=="black" and sc<best_score):
                                    best_score, best=sc,("C",r,c,tr,tc)
        # quantum sampling
        samples=0
        while samples<max_q:
            r,c=random.randrange(8),random.randrange(8)
            p=self.piece_any(r,c)
            if p and p.color==color and p.kind!="K":
                leg=[(tr,tc) for tr in range(8) for tc in range(8)
                     if self._legal(self.branches[0],p,r,c,tr,tc)]
                if len(leg)>=2:
                    t1,t2=random.sample(leg,2); seed=random.randrange(2**32)
                    sim=copy.deepcopy(self); sim.collapse_on(r,c,seed); sim.quantum(r,c,*t1,*t2)
                    sc=sim.evaluate(color,4,12)
                    if (color=="white" and sc>best_score) or (color=="black" and sc<best_score):
                        best_score, best=sc,("Q",r,c,*t1,*t2,seed)
                    samples+=1
        return best

# ── GUI ──
class GUI:
    def __init__(self):
        self.board=Board()
        self.vs_ai=messagebox.askyesno("Opponent","Play against computer?")
        if self.vs_ai:
            self.color="white" if messagebox.askyesno("Colour","Play as White?") else "black"
            self.opponent="black" if self.color=="white" else "white"; self.is_host=False
        else:
            host=simpledialog.askstring("Network","'host' or IP:")
            if host.lower()=="host":
                self.is_host,self.color,self.opponent=True,"white","black"
            else:
                self.is_host,self.host_ip=False,host.strip(),"black","white"
        self.flip=(self.color=="black")

        self.root=tk.Tk(); self.root.title("Quantum Chess")
        self.canvas=tk.Canvas(self.root,width=8*S,height=8*S); self.canvas.pack()
        self.q=tk.BooleanVar(); tk.Checkbutton(self.root,text="Q-move",variable=self.q).pack(anchor="w")
        self.status=tk.Label(self.root,font=("Arial",12)); self.status.pack()
        self.sel=self.q1=None; self.hl=[]; self.sending=False

        self.canvas.bind("<Button-1>",self.click)
        self.draw(); self.stat(); threading.Thread(target=self.loop,daemon=True).start()

    # coord helpers
    def rc(self,x,y): sr,sc=y//S,x//S; return (7-sr,7-sc) if self.flip else (sr,sc)
    def scr(self,r,c): sr,sc=(7-r,7-c) if self.flip else (r,c); return sc*S,sr*S
    def enc(self,r,c): return f"{FILES[c]}{8-r}"
    def dec(self,s):   return 8-int(s[1]), FILES.index(s[0])

    # drawing
    def draw(self):
        self.canvas.delete("all")
        light,dark="#EEEED2","#769656"
        for r in range(8):
            for c in range(8):
                x0,y0=self.scr(r,c); self.canvas.create_rectangle(x0,y0,x0+S,y0+S,
                    fill=light if (r+c)%2==0 else dark,outline="")
        for r,c in self.hl:
            x0,y0=self.scr(r,c); self.canvas.create_rectangle(x0,y0,x0+S,y0+S,
                fill="yellow",stipple="gray25",outline="")
        for r in range(8):
            for c in range(8):
                glyph=None
                if any(b[r][c] for b in self.board.branches):
                    mp=self.board.merged(r,c); glyph=mp.char() if mp else "?"
                if glyph:
                    x0,y0=self.scr(r,c)
                    self.canvas.create_text(x0+S//2,y0+S//2,text=glyph,font=("Arial",36))

    def stat(self):
        self.status.config(text=f"{self.color} | Turn:{self.board.turn} | {'Q' if self.q.get() else 'C'} | {'AI' if self.vs_ai else 'LAN'}")

    def moves(self,r,c):
        p=self.board.piece_any(r,c)
        if not p: return []
        return [(tr,tc) for tr in range(8) for tc in range(8)
                if self.board._legal(self.board.branches[0],p,r,c,tr,tc)]

    # click
    def click(self,e):
        r,c=self.rc(e.x,e.y); p=self.board.piece_any(r,c)
        if self.board.turn!=self.color: return
        if self.q.get():                                       # quantum mode
            if p and p.kind=="K": return
            if not self.sel:
                if p and p.color==self.color: self.sel=(r,c); self.hl=self.moves(r,c)
            elif not self.q1:
                if (r,c) in self.hl: self.q1=(r,c)
            else:
                if (r,c) in self.hl and (r,c)!=self.q1:
                    sr,sc=self.sel; t1r,t1c=self.q1; t2r,t2c=r,c; seed=random.randrange(2**32)
                    self.board.collapse_on(sr,sc,seed); self.board.quantum(sr,sc,t1r,t1c,t2r,t2c)
                    if not self.vs_ai:
                        self.send(f"Q:{self.enc(sr,sc)}{self.enc(t1r,t1c)}:{self.enc(sr,sc)}{self.enc(t2r,t2c)}:{seed}")
                    self.after()
                self.clear()
        else:                                                   # classical mode
            if not self.sel:
                if p and p.color==self.color: self.sel=(r,c); self.hl=self.moves(r,c)
            else:
                if (r,c) in self.hl:
                    sr,sc=self.sel; seed=random.randrange(2**32)
                    self.board.collapse_on(r,c,seed); self.board.classical(sr,sc,r,c)
                    if not self.vs_ai:
                        self.send(f"C:{self.enc(sr,sc)}{self.enc(r,c)}")
                    self.after()
                self.clear()
        self.draw(); self.stat()

    def clear(self): self.sel=self.q1=None; self.hl=[]

    def after(self): self.draw(); self.stat()

    # networking helpers
    def send(self,msg):
        self.sending=True
        def t():
            try:
                if self.is_host: lan_socket.server_mode(msg.encode(),"white")
                else:            lan_socket.client_mode(msg.encode(),"white",self.host_ip)
            finally: self.sending=False
        threading.Thread(target=t,daemon=True).start()

    def recv(self):
        if self.is_host: return lan_socket.server_mode(b"","black")
        return lan_socket.client_mode(b"","black",self.host_ip)

    def apply(self,msg):
        if msg.startswith("C"):
            sr,sc=self.dec(msg[2:4]); tr,tc=self.dec(msg[4:6])
            self.board.collapse_on(tr,tc,random.randrange(2**32)); self.board.classical(sr,sc,tr,tc)
        else:
            _,p1,p2,seed=msg.split(":"); seed=int(seed)
            sr,sc=self.dec(p1[:2]); t1r,t1c=self.dec(p1[2:]); t2r,t2c=self.dec(p2[2:])
            self.board.collapse_on(sr,sc,seed); self.board.quantum(sr,sc,t1r,t1c,t2r,t2c)
        self.after()

    # main loop
    def loop(self):
        while True:
            if self.vs_ai and self.board.turn==self.opponent:
                mv=self.board.best_ai_move(self.opponent)
                if mv is None:
                    messagebox.showinfo("Game over","AI has no legal move")
                    return
                if mv[0]=="C":
                    _,sr,sc,tr,tc=mv
                    self.board.collapse_on(tr,tc,random.randrange(2**32)); self.board.classical(sr,sc,tr,tc)
                else:
                    _,sr,sc,t1r,t1c,t2r,t2c,seed=mv
                    self.board.collapse_on(sr,sc,seed); self.board.quantum(sr,sc,t1r,t1c,t2r,t2c)
                self.after()
            elif not self.vs_ai and not self.sending and self.board.turn==self.opponent:
                m=self.recv(); self.root.after(0,self.apply,m) if m else None
            time.sleep(0.05)

    def run(self): self.root.mainloop()

# ── run ──
if __name__=="__main__":
    GUI().run()
