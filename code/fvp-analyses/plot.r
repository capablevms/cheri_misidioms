#!/usr/bin/Rscript

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

library(ggplot2)

data <- read.csv(file='stdin', header=TRUE)

colours <- array(dimnames=list(data$ELF:data$Symbol), data=data$Colour)

ggplot(data,
       aes(x = ABI, y = Normalised.Instruction.Count, fill = ELF:Symbol)) +
  scale_fill_manual(values=colours) +
  geom_bar(stat = 'identity', position = 'stack', colour="black") +
  facet_grid(~ Benchmark) +
  scale_y_continuous(expand=c(0,0),
                     breaks=seq(0,2,1/4),
                     limits=c(0,1.59),     # TODO: Calculate this automatically.
                     # Hack to put a box around all facets (rather than each
                     # panel individually): pretend we have a right axis too.
                     sec.axis=dup_axis(breaks=0)) +
  ylab("Instruction count (normalised to hybrid)") +
  theme(panel.spacing = unit(0, "mm"),
        axis.text.x = element_text(angle=90, vjust=0.5),
        axis.title.x = element_blank(),
        legend.title = element_blank(),
        strip.text = element_text(size=7),
        #strip.background = element_rect(fill="white", colour="grey50", size=1),
        strip.background = element_rect(fill=NA, colour=NA),
        panel.background = element_rect(fill="white", colour=NA),
        # Hide all but the line of the right axis (used as a border).
        axis.title.y.right = element_blank(),
        axis.text.y.right = element_blank(),
        axis.ticks.y.right = element_blank(),
        axis.line = element_line(colour="black", size=.5),  # This comes out double thickness (1).
        panel.grid = element_blank()) +
  # Hack: draw the top of the box.
  geom_hline(yintercept=1.59, colour="black", size=1)
ggsave("../../fig/fvp-stats.pdf",width=5.5)
