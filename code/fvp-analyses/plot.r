#!/usr/bin/Rscript

# SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: MIT OR Apache-2.0

library(ggplot2)

data <- read.csv(file='stdin', header=TRUE)

colours <- array(dimnames=list(data$ELF:data$Symbol), data=data$Colour)

ggplot(data,
       aes(x = ABI, y = Instruction.Count, fill = ELF:Symbol)) +
  scale_fill_manual(values=colours) +
  geom_bar(stat = 'identity', position = 'stack') +
  facet_grid(~ Benchmark) +
  theme(panel.spacing = unit(0, "lines"))
ggsave("../../fig/fvp-stats.pdf")
