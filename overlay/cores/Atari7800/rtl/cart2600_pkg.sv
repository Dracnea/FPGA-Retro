// cart2600_pkg -- the 2600 bank-switching enum that upstream declares at file
// scope in detect2600.sv and uses from cart2600.sv. Quartus shares the
// compilation-unit scope between files; Vivado does not, so it is a package here
// and both files import it. Values and order are upstream's, unchanged.
// SPDX-License-Identifier: GPL-2.0 (upstream Atari7800_MiSTer)
package cart2600_pkg;
typedef enum bit[4:0] { 
	BANK00, BANKF8, BANKF6, BANKFE, BANKE0,   BANK3F,   BANKF4,  BANKP2,
	BANKFA, BANKCV, BANK2K, BANKUA, BANKE7,   BANKF0,   BANK32,  BANKAR,
	BANK3E, BANKSB, BANKWD, BANKEF, BANKJANE, BANKDPCP, BANKCTY, BANKCDF,
	BANKBUS, BANKFA2, BANKELF, BANKEND
} bss_type ;
endpackage
