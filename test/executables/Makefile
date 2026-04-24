CRACKME_BIN = basic_crackme/test_basic_crackme
FP_BIN      = floating_point/test_fp
EXT_BIN     = extended_registers/test_extended_registers

all: $(CRACKME_BIN) $(FP_BIN) $(EXT_BIN)

$(CRACKME_BIN): basic_crackme/test_basic_crackme.c
	gcc -o $@ $<

$(FP_BIN): floating_point/test_fp.c
	gcc -o $@ $<

$(EXT_BIN): extended_registers/test_extended_registers.c
	gcc -o $@ $<

clean:
	rm -f $(CRACKME_BIN) $(FP_BIN) $(EXT_BIN)