import { Component, Input, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { Cart, CartItem } from 'src/app/models/cart.model';
import { AuthService } from 'src/app/authentication/authentication.service';
import { CartService } from 'src/app/services/cart.service';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html'
})
export class HeaderComponent implements OnInit{

  private _cart: Cart = { items: [] }
  itemsQuantity = 0;
  isLoggedIn = false;

  @Input() 
  
  public get cart() : Cart {
    return this._cart;
  }
  
  public set cart(cart : Cart) {
    this._cart = cart;
    this.itemsQuantity 
      = cart
        .items
        .map( (item) =>item.quantity )
        .reduce( (previous, current) => previous + current, 0 );
  }
  
  

  constructor(private _cartService: CartService,
    private authService: AuthService,
    private router: Router){
  }
  ngOnInit(): void {
    this.isLoggedIn = this.authService.isUserLoggedIn();
  }

  getTotal( items: Array<CartItem> ):number{
    return this._cartService.getTotal(items);
  }

  onClearCart(){
    this._cartService.clearCart();
  }

  logout(){
    this.authService.logout();
    this.isLoggedIn = false;
    this.router.navigate(['home']);
  }
 
}
