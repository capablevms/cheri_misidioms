.SUFFIXES: .ltx .ps .pdf .svg

.svg.pdf:
	inkscape --export-pdf=$@ $<

LATEX_FILES = cheri_misidioms.ltx

DIAGRAMS =

all: cheri_misidioms.pdf

clean:
	rm -rf ${DIAGRAMS} ${DIAGRAMS:S/.pdf/.eps/}
	rm -rf cheri_misidioms.aux cheri_misidioms.bbl cheri_misidioms.blg cheri_misidioms.dvi cheri_misidioms.log cheri_misidioms.ps cheri_misidioms.pdf cheri_misidioms.toc cheri_misidioms.out cheri_misidioms.snm cheri_misidioms.nav cheri_misidioms.vrb cheri_misidioms_preamble.fmt texput.log

cheri_misidioms.pdf: bib.bib ${LATEX_FILES} ${DIAGRAMS} cheri_misidioms_preamble.fmt code/*.c
	pdflatex cheri_misidioms.ltx
	bibtex cheri_misidioms
	pdflatex cheri_misidioms.ltx
	pdflatex cheri_misidioms.ltx

cheri_misidioms_preamble.fmt: cheri_misidioms_preamble.ltx
	set -e; \
	  tmpltx=`mktemp`; \
	  cat ${@:fmt=ltx} > $${tmpltx}; \
	  grep -v "%&${@:_preamble.fmt=}" ${@:_preamble.fmt=.ltx} >> $${tmpltx}; \
	  pdftex -ini -jobname="${@:.fmt=}" "&pdflatex" mylatexformat.ltx $${tmpltx}; \
	  rm $${tmpltx}

bib.bib: softdevbib/softdev.bib
	softdevbib/bin/prebib softdevbib/softdev.bib > bib.bib

softdevbib-update: softdevbib
	cd softdevbib && git pull

softdevbib/softdev.bib: softdevbib

softdevbib:
	git clone https://github.com/softdevteam/softdevbib.git
