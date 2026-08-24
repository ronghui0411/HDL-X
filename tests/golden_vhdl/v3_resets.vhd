library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3AsyncReset is
    port (
        clk : in std_logic;
        rst_n : in std_logic;
        enable : in std_logic;
        d : in std_logic;
        q : out std_logic
    );
end entity V3AsyncReset;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3AsyncReset is
begin
    async_p : process(clk, rst_n)
    begin
        if rst_n = '0' then
            q <= '0';
        else
            if rising_edge(clk) then
                if enable = '1' then
                    q <= d;
                end if;
            end if;
        end if;
    end process async_p;
end architecture rtl;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3SyncReset is
    port (
        clk : in std_logic;
        rst : in std_logic;
        d : in std_logic;
        q : out std_logic
    );
end entity V3SyncReset;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3SyncReset is
begin
    sync_p : process(clk)
    begin
        if falling_edge(clk) then
            if rst = '1' then
                q <= '0';
            else
                q <= d;
            end if;
        end if;
    end process sync_p;
end architecture rtl;
