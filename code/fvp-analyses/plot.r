#!/usr/bin/Rscript

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

library(ggplot2)

data <- read.csv(file='stdin', header=TRUE)

colours <- array(dimnames=list(data$ELF:data$Symbol), data=data$Colour)

ggplot(data,
       aes(x = ABI, y = Normalised.Instruction.Count, fill = ELF:Symbol)) +
  scale_fill_manual(values=colours) +
  geom_bar(stat = 'identity', position = 'stack', colour="grey25") +
  facet_grid(~ Benchmark) +
  scale_y_continuous(expand=c(0,0),
                     breaks=seq(0,2,1/4),
                     limits=c(0,1.59)) +   # TODO: Calculate this automatically.
  ylab("Instruction count (normalised to hybrid)") +
  theme(panel.spacing = unit(0, "lines"),
        strip.background = element_rect(fill="white", colour=NA),
        panel.background = element_rect(fill="white", colour=NA),
        panel.border = element_rect(fill=NA, colour="grey50"),
        panel.grid = element_blank())
ggsave("../../fig/fvp-stats.pdf")
