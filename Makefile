.SUFFIXES: .ltx .ps .pdf .svg

.svg.pdf:
	inkscape --export-pdf=$@ $<

LATEX_FILES = cheri_misidioms.ltx

DIAGRAMS =

all: cheri_misidioms.pdf

clean:
	rm -rf ${DIAGRAMS} ${DIAGRAMS:S/.pdf/.eps/}
	rm -rf cheri_misidioms.aux cheri_misidioms.bbl cheri_misidioms.blg cheri_misidioms.dvi cheri_misidioms.log cheri_misidioms.ps cheri_misidioms.pdf cheri_misidioms.toc cheri_misidioms.out cheri_misidioms.snm cheri_misidioms.nav cheri_misidioms.vrb texput.log

cheri_misidioms.pdf: bib.bib ${LATEX_FILES} ${DIAGRAMS}
	pdflatex cheri_misidioms.ltx
	bibtex cheri_misidioms
	pdflatex cheri_misidioms.ltx
	pdflatex cheri_misidioms.ltx

bib.bib: softdevbib/softdev.bib
	softdevbib/bin/prebib softdevbib/softdev.bib > bib.bib

softdevbib-update: softdevbib
	cd softdevbib && git pull

softdevbib/softdev.bib: softdevbib

softdevbib:
	git clone https://github.com/softdevteam/softdevbib.git
