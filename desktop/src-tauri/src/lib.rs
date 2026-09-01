//! Library entry for the Tauri 2 desktop binary.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    calypso_desktop_lib::run();
}
