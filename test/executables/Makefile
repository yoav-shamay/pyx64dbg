CRACKME_BIN = basic_crackme/test_basic_crackme
FP_BIN      = floating_point/test_fp
EXT_BIN     = extended_registers/test_extended_registers
NON_PIE_BIN = non_pie/test_non_pie
STATIC_LINKED_BIN = static_linked/test_static_linked

all: $(CRACKME_BIN) $(FP_BIN) $(EXT_BIN) $(NON_PIE_BIN) $(STATIC_LINKED_BIN)

$(CRACKME_BIN): basic_crackme/test_basic_crackme.c
	gcc -o $@ $<

$(FP_BIN): floating_point/test_fp.c
	gcc -o $@ $<

$(EXT_BIN): extended_registers/test_extended_registers.c
	gcc -o $@ $<

$(NON_PIE_BIN): non_pie/test_non_pie.c
	gcc -o $@ $< -no-pie

$(STATIC_LINKED_BIN): static_linked/test_static_linked.c
	gcc -o $@ $< -static

clean:
	rm -f $(CRACKME_BIN) $(FP_BIN) $(EXT_BIN) $(NON_PIE_BIN) $(STATIC_LINKED_BIN)