/**
 * Side-effect imports of every feature command file, one line each, alphabetical. Each file adds
 * its commands to the shared list (see commands.ts). main.tsx imports this once. actions.ts must
 * not: a cmd file may import actions.ts, so that would be a cycle.
 */
import "./branch";
import "./draw";
import "./fills";
import "./importArt";
import "./lettering";
import "./lines";
import "./repair";
import "./shapes";

export {};
