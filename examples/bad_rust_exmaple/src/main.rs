fn main() {
    let numbers = vec![1, 2, 3, 4, 5];

    // Clippy: unnecessary length comparison
    if numbers.len() > 0 {
        println!("The vector is not empty!");
    }

    // Clippy: needless range loop
    for i in 0..numbers.len() {
        println!("Number: {}", numbers[i]);
    }

    let name = String::from("Clippy");

    // Clippy: unnecessary reference
    print_name(&name);

    // Clippy: unnecessary return
    let result = add_numbers(10, 20);
    println!("Result: {}", result);

    // Clippy: useless vec
    let colors = vec!["red", "green", "blue"];

    println!("First color: {}", colors[0]);
}

fn print_name(name: &String) {
    println!("Hello, {}!", name);
}

fn add_numbers(a: i32, b: i32) -> i32 {
    return a + b;
}
