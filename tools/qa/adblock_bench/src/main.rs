// Copyright 2026 KuchiSofts. Use of this source code is governed by a BSD-style license that can be found in the LICENSE file.
// Thoron native ad-blocking spike (ROADMAP P5.13): how fast and how big is adblock-rust with the lists
// Thoron ships? Offline; reads local list files and a local request log.
use std::alloc::{GlobalAlloc, Layout, System};
use std::io::{BufRead, BufReader};
use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};
use std::time::Instant;

use adblock::lists::{FilterSet, ParseOptions};
use adblock::request::Request;
use adblock::Engine;

struct Counting;
static LIVE: AtomicUsize = AtomicUsize::new(0);
static PEAK: AtomicUsize = AtomicUsize::new(0);
unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, l: Layout) -> *mut u8 {
        let p = unsafe { System.alloc(l) };
        if !p.is_null() {
            let now = LIVE.fetch_add(l.size(), Relaxed) + l.size();
            PEAK.fetch_max(now, Relaxed);
        }
        p
    }
    unsafe fn dealloc(&self, p: *mut u8, l: Layout) {
        unsafe { System.dealloc(p, l) };
        LIVE.fetch_sub(l.size(), Relaxed);
    }
}
#[global_allocator]
static A: Counting = Counting;

fn mb(b: usize) -> f64 { b as f64 / 1048576.0 }

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let (requests_path, limit) = (&args[1], args[2].parse::<usize>().unwrap());
    let lists = &args[3..];

    let parse_start = Instant::now();
    let mut set = FilterSet::new(false);
    let mut rules = 0usize;
    for path in lists {
        let text = std::fs::read_to_string(path).expect("list");
        rules += text.lines().count();
        set.add_filter_list(text, ParseOptions::default());
    }
    let parse_ms = parse_start.elapsed().as_secs_f64() * 1000.0;
    let t = Instant::now();
    let engine = Engine::new_with_filter_set(set);
    let build_ms = t.elapsed().as_secs_f64() * 1000.0;
    let engine_mem = LIVE.load(Relaxed);          // the list texts and the filter set are gone: this is the engine
    let load_start = Instant::now();
    let restored = { let mut e = Engine::default(); e.deserialize(&engine.serialize()).expect("restore"); e };
    let restore_ms = load_start.elapsed().as_secs_f64() * 1000.0;
    drop(restored);
    let serialized = engine.serialize().len();

    let file = std::fs::File::open(requests_path).expect("requests");
    let mut reqs = Vec::new();
    for line in BufReader::new(file).lines().map_while(Result::ok) {
        if reqs.len() >= limit { break; }
        let v: serde_json::Value = match serde_json::from_str(&line) { Ok(v) => v, Err(_) => continue };
        let (Some(url), Some(src), Some(cpt)) = (v["url"].as_str(), v["frameUrl"].as_str(), v["cpt"].as_str()) else { continue };
        if let Ok(r) = Request::new(url, src, cpt, "GET") { reqs.push(r); }
    }
    let mut times = Vec::with_capacity(reqs.len());
    let mut blocked = 0usize;
    let all = Instant::now();
    for r in &reqs {
        let t = Instant::now();
        if engine.check_network_request(r).should_block() { blocked += 1; }
        times.push(t.elapsed().as_nanos() as u64);
    }
    let total_ms = all.elapsed().as_secs_f64() * 1000.0;
    times.sort_unstable();
    let pct = |p: f64| times[((times.len() as f64 * p) as usize).min(times.len() - 1)] as f64 / 1000.0;
    println!("{{\"rules_lines\":{rules},\"parse_ms\":{parse_ms:.0},\"build_ms\":{build_ms:.0},\"restore_ms\":{restore_ms:.0},\"engine_heap_mb\":{:.1},\"peak_heap_mb\":{:.1},\"serialized_mb\":{:.1},\
\"requests\":{},\"blocked\":{blocked},\"blocked_pct\":{:.1},\"total_ms\":{total_ms:.0},\"avg_us\":{:.2},\"p50_us\":{:.2},\"p99_us\":{:.2},\"max_us\":{:.1}}}",
        mb(engine_mem), mb(PEAK.load(Relaxed)), mb(serialized), reqs.len(), blocked as f64 * 100.0 / reqs.len() as f64,
        total_ms * 1000.0 / reqs.len() as f64, pct(0.5), pct(0.99), pct(1.0) * 1.0);
}
