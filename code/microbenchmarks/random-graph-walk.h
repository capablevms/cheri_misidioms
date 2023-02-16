// SPDX-FileCopyrightText: Copyright 2023 Arm Limited and/or its affiliates <open-source-office@arm.com>
// SPDX-License-Identifier: MIT OR Apache-2.0

#define N_EXITS 7
struct Node {
    struct Node* exits[N_EXITS];
    uint64_t value;
};

struct Node * alloc_node(void) {
    struct Node * node = malloc(sizeof(struct Node));
    for (size_t i = 0; i < N_EXITS; i++) {
        node->exits[i] = NULL;
    }
    node->value = random();
    return node;
}

void connect_nodes(struct Node * nodes, size_t n_nodes) {
    for (size_t n = 0; n < n_nodes; n++) {
        nodes[n].value = random();
        // Ensure that the graph is connected.
        nodes[n].exits[0] = &nodes[(n + 1) % n_nodes];
        for (size_t e = 1; e < N_EXITS; e++) {
            nodes[n].exits[e] = &nodes[random() % n_nodes];
        }
    }

    printf("Connected %zu nodes (%zu bytes).\n", n_nodes, sizeof(struct Node) * n_nodes);
}

struct Node * generate_n(size_t n_nodes) {
    struct Node * nodes = malloc(sizeof(struct Node) * n_nodes);
    assert(nodes != NULL);

    connect_nodes(nodes, n_nodes);
    return nodes;
}

struct Node * generate_with_max_size(size_t size_in_bytes) {
    return generate_n(size_in_bytes / sizeof(struct Node));
}

uint64_t walk(struct Node * node, size_t visits) {
    uint64_t value = 0;
    for (size_t v = 0; v < visits; v++) {
        value += node->value;
        //printf("Visiting node %p with value 0x%016" PRIx64 ". Taking exit %zu...\n",
        //       node, node->value, value % N_EXITS);
        node = node->exits[value % N_EXITS];
    }
    return value;
}

