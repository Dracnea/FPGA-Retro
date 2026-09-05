-- cpu_mul -- N64 CPU 64x64 multiplier, Vivado replacement for upstream/rtl/cpu_mul.vhd.
--
-- Upstream wraps altera_mult_add with ~250 generics to get: one multiplier,
-- 64 x 64 -> 128, sign selected at runtime on both operands by `sign`
-- (port_signa/port_signb = PORT_USED), result registered on clock0. That is all
-- this is. Same entity and ports, so nothing else in the core changes.
-- SPDX-License-Identifier: BSD-2-Clause
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity cpu_mul is
   port
   (
      clk       : in  std_logic;
      sign      : in  std_logic;
      value1_in : in  std_logic_vector(63 downto 0);
      value2_in : in  std_logic_vector(63 downto 0);
      result    : out std_logic_vector(127 downto 0)
   );
end entity;

architecture arch of cpu_mul is
   -- one extra bit each so a single signed multiply covers both interpretations
   signal a_ext : signed(64 downto 0);
   signal b_ext : signed(64 downto 0);
begin
   a_ext <= signed((sign and value1_in(63)) & value1_in);
   b_ext <= signed((sign and value2_in(63)) & value2_in);
   process (clk)
      variable p : signed(129 downto 0);
   begin
      if rising_edge(clk) then
         p := a_ext * b_ext;
         result <= std_logic_vector(p(127 downto 0));
      end if;
   end process;
end architecture;
